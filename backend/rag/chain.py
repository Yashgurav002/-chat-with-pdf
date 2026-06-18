import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

load_dotenv()

_llm = None


def _get_llm():
    global _llm
    if _llm is not None:
        return _llm

    mode = os.getenv("MODE", "production")
    if mode == "local":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        _llm = ChatOllama(model="llama3.2", base_url=base_url)
    else:
        _llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"))
    return _llm


def _format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


def build_chain(retriever, chat_history: list = None):
    chat_history = chat_history or []

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Answer only from the provided context. "
            "If you don't know, say so.\n\nContext:\n{context}",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}"),
    ])

    def build_input(question: str):
        docs = retriever.invoke(question)
        return {
            "context": _format_docs(docs),
            "chat_history": chat_history,
            "question": question,
        }

    return (
        RunnableLambda(build_input)
        | prompt
        | _get_llm()
        | StrOutputParser()
    )