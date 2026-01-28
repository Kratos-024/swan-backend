from langgraph.graph import START,StateGraph,END,add_messages
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from typing import Optional, TypedDict, Annotated, List
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from dotenv import load_dotenv
load_dotenv()
from GoogleDrive import DriveAPI
from PersistentMem import PersistentMem
from langchain_core.messages import HumanMessage, AIMessage,BaseMessage
drive = DriveAPI()

def make_drive_tool():
    """The Google drive api caller to get Documents"""
    documents = drive.get_documents()
    return documents


class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    pdf_query_bool : Optional[bool]
    pdf_query: Annotated[List[BaseMessage], add_messages]
class PdfSession:
    def __init__(self,state:ChatState):
        self.pdf_path = 'path'
    def initiate_chat_session(self,state:ChatState):
        message = state['messages'][-1]
        
        if not (state['pdf_query']):
                documents = make_drive_tool()
                documents = [(doc['name'],doc['type']) for doc in documents]
        
        template = ChatPromptTemplate.from_messages([
            ("system", 
            "You are a PDF query assistant. I will provide a list of documents from Drive. "
            "Format the documents only as a numbered list showing their name and type, like:\n"
            "After listing the documents, ask the user: 'Which document do you want me to use as context?'"
            ),
            ("human", "{messages}\nDocuments:\n{documents}")
        ])

        prompt = template.invoke({'messages':message.content,'documents':documents})
        result = self.chat_model.invoke(prompt)
        
        state['pdf_query'].append(AIMessage(content=result.content))
        

class Chat_HuggingFaceController:
    def __init__(self,model,DB_URI):
        llm = HuggingFaceEndpoint(model=model)
        self.chat_model = ChatHuggingFace(llm=llm)
        self.DB_URI = DB_URI
        self.workflow_log()
    def give_response(self,state:ChatState):
        message = state['messages'][-1]

        template = ChatPromptTemplate.from_messages([
            ("system", "You are a teacher. Answer the question asked by student."),
        MessagesPlaceholder(variable_name="chat_history"),('human',"{messages}")
        ])
        prompt = template.invoke({'messages':message.content, 'chat_history':state['messages'][:-1]})

        result = self.chat_model.invoke(prompt)

        return {
        "messages": [result]
    }

    def workflow_log(self):
        graph_state = StateGraph(ChatState)
        graph_state.add_node('give_response',self.give_response)
        graph_state.add_node('set_pdf_query_bool',self.set_pdf_query_bool)
        graph_state.add_node('query_pdf',self.query_pdf)

        graph_state.add_edge(START,"set_pdf_query_bool")
        graph_state.add_conditional_edges('set_pdf_query_bool',self.query_pdf_handler,{
            'query_pdf':'query_pdf',
            'give_response':"give_response"
        
        })
        graph_state.add_edge('query_pdf',END)
        graph_state.add_edge('give_response',END)
        perstMem = PersistentMem(self.DB_URI)
        checkpointer = perstMem.postgresDB()
        self.workflow = graph_state.compile(checkpointer=checkpointer)
    def set_pdf_query_bool(self,state:ChatState)->ChatState:
        message = state['messages'][-1]

        template = ChatPromptTemplate.from_messages([
            ("system", "You are a bot i created you, when user message involved '/pdf' in starting return True else return False"),
            ('human',"{messages}")
        ])
        prompt = template.invoke({'messages':message.content})

        result = self.chat_model.invoke(prompt)
        state['pdf_query_bool']=True if result.content == "True" else False

        
        return state

    def query_pdf(self,state:ChatState)->ChatState:
        message = state['messages'][-1]
        
        if not (state['pdf_query']):
                documents = make_drive_tool()
                documents = [(doc['name'],doc['type']) for doc in documents]
        
        template = ChatPromptTemplate.from_messages([
            ("system", 
            "You are a PDF query assistant. I will provide a list of documents from Drive. "
            "Format the documents only as a numbered list showing their name and type, like:\n"
            "After listing the documents, ask the user: 'Which document do you want me to use as context?'"
            ),
            ("human", "{messages}\nDocuments:\n{documents}")
        ])

        prompt = template.invoke({'messages':message.content,'documents':documents})
        result = self.chat_model.invoke(prompt)
        
        state['pdf_query'].append(AIMessage(content=result.content))
        
        
        
        return state


    def chat(self,user_query,thread_id):
        config = {"configurable": {"thread_id": thread_id}}
        user_query=HumanMessage(content=user_query)
     
        result = self.workflow.invoke({'messages':[user_query]},config=config)
        return result['messages'][-1].content



    def query_pdf_handler(self,state:ChatState):
        if state['pdf_query_bool'] and state['pdf_session'] != None:
            self.pdf_session = PdfSession(state)
            
        elif state['pdf_query_bool']:
            state['pdf_session']='started'
            return 'query_pdf'
        else:
            
            return 'give_response'