from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

class PersistentMem:
    def __init__(self,DB_URI):
        self.DB_URI = DB_URI
        pool = ConnectionPool(conninfo=DB_URI,kwargs={"autocommit": True})
        self.checkpointer = PostgresSaver(pool)
        self.checkpointer.setup()  
    def postgresDB(self):
        return self.checkpointer

 
  