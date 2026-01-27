from langgraph.graph import START,StateGraph,END,add_messages
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from typing import TypedDict, Annotated, List
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from dotenv import load_dotenv
load_dotenv()
from PersistentMem import PersistentMem
from langchain_core.messages import HumanMessage, AIMessage,BaseMessage



class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

class Chat_HuggingFaceController:
    def __init__(self,model,DB_URI):
        llm = HuggingFaceEndpoint(model=model)
        self.chat_model = ChatHuggingFace(llm=llm)
        self.DB_URI = DB_URI
        self.workflow_log()
    def give_response(self,state:ChatState):
        message = state['messages'][-1]
        template = ChatPromptTemplate.from_messages([
("system", """You are an encouraging and patient High School Teacher. 
Your goal is to guide the student through concepts using the Socratic method.

Rules:
1. If the student gives a very short answer, acknowledge it warmly and ask a 
   probing follow-up question to help them expand their thinking.
2. Use a professional yet friendly tone (e.g., "Great start!", "Tell me more about that").
3. Keep your own responses concise so the student doesn't feel overwhelmed.
4. If the student is stuck, provide a small hint or an analogy rather than 
   just giving the full answer immediately."""),MessagesPlaceholder(variable_name="chat_history"),('human',"{messages}")
        ])
        prompt = template.invoke({'messages':message.content, 'chat_history':state['messages'][:-1]})
        result = self.chat_model.invoke(prompt)

        return {"messages": [result]}
    def workflow_log(self):
        graph_state = StateGraph(ChatState)
        graph_state.add_node('give_response',self.give_response)

        graph_state.add_edge(START,"give_response")
        graph_state.add_edge('give_response',END)
        perstMem = PersistentMem(self.DB_URI)
        checkpointer = perstMem.postgresDB()
        self.workflow = graph_state.compile(checkpointer=checkpointer)
    def chat(self,user_query,thread_id):
        config = {"configurable": {"thread_id": thread_id}}
        user_query=HumanMessage(content=user_query)
        print(user_query.content)
        result = self.workflow.invoke({'messages':[user_query]},config=config)
        return result['messages'][-1].content



