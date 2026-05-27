from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
import uuid
import os
import opencc
os.environ['KMP_DUPLICATE_LIB_OK']='True'

import markdown

import pytube as pt
#import whisper
import whisper_timestamped as whisper


import threading

from tenacity import (
    retry,
    stop_after_attempt,
    wait_chain,
    wait_exponential,
    wait_fixed,
    wait_random_exponential,
)  # for exponential backoff\
    
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
    
    
TSP = dict()    
    

class Node:
    def __init__(self, name):
        self.name = name
        self.mark = ""
        self.child = None
        self.sibling = None
        #self.parent = None
        
class LinkedList:
    def __init__(self):
        self.head = None
        
    def insertTitle(self, title):
        new_node = Node(title)
        new_node.mark = "#"
        self.head = new_node
        return new_node
     
    def insertNode(self, parent, nodes, conversational_rag_chain, session_id):
        if parent.child is not None:
            return
        former_node = None
        for n in nodes:
            new_node = Node(n)
            new_node.mark = parent.mark + "#"
            DEFINITION_THREAD.append(threading.Thread(target = _store_def, args = (conversational_rag_chain, new_node.name, session_id)))
            if parent.child is None:
                parent.child = new_node
            if former_node is None:
                former_node = new_node
            else:
                former_node.sibling = new_node
                former_node = new_node
                
    def searchParent(self, name):
        current_node = self.head
        start = -1
        end = -1
        queue = []
        while(current_node):
            print(current_node.name + ":" + name)
            if current_node.name == name:
                return current_node
            #print(current_node.mark + " " + current_node.name)
            if current_node.sibling is not None:
                if current_node.child is not None:
                    if start < 0:
                        start += 1
                    end += 1
                    queue.append(current_node.child)
                current_node = current_node.sibling
            else:
                if current_node == self.head:
                    current_node = current_node.child
                elif end >= start:
                    current_node = queue[start]
                    start += 1
                else:
                    break
        return None
        
    def printLL(self, conversational_rag_chain, session_id, knowledge_base_forTSP):
        global TSP
        current_node = self.head
        top = -1
        stack = []
        while(current_node):
            if knowledge_base_forTSP:
                docs = knowledge_base_forTSP.similarity_search(current_node.name)
                print(docs)
                ANS.append(current_node.mark + " " + current_node.name + " " + str(TSP[docs[0].page_content]) + "\n")
            else:
                ANS.append(current_node.mark + " " + current_node.name + "\n")
            
            if current_node.name != self.head.name:
                if current_node.name in STORE_DEFINITION:
                    ANS.append(STORE_DEFINITION[current_node.name] + "\n")
                else:
                    ANS.append("definition is not found.\n")
            
            if current_node.child is not None:
                if current_node.sibling is not None:
                    top += 1
                    stack.append(current_node.sibling)
                current_node = current_node.child
            elif current_node.sibling is not None:
                current_node = current_node.sibling
            else:
                if top >= 0:
                    current_node = stack[top]
                    top -= 1
                    stack.pop()
                else:
                    break
                

                

    
# From the LangChain documentation
CONDENSE_PROMPT = """Given a chat history and the latest user question \
which might reference context in the chat history, formulate a standalone question \
which can be understood without the chat history. Do NOT answer the question, \
just reformulate it if needed and otherwise return it as is.
"""

QA_PROMPT = """You are an assistant for question-answering tasks. \
Use the following pieces of retrieved context to answer the question. \
If you don't know the answer, just say that you don't know. \
Use three sentences maximum and keep the answer concise.\

{context}
"""

# Lazy implementation to maintain chat history of different ids
STORE = dict()
STORE_DEFINITION = dict()
ANS = []
WORK = []
WORK_THREAD = []
DEFINITION_THREAD = []
front = -1
reer = -1


def _get_memory(session_id=None) -> BaseChatMessageHistory:
    """Returns memory of the session

    :param session_id: The keyname is magic unless override `history_factory_config`
                       in `RunnableWithMessageHistory`
    :return:
    """
    if session_id is None:
        session_id = str(uuid.uuid4())
    if session_id not in STORE:
        STORE[session_id] = ChatMessageHistory()
    return STORE[session_id]

#@retry(wait=wait_random_exponential(multiplier=1, max=10))
def _store_def(conversational_rag_chain, node, session_id):
    print("====== conversation pass 1 ======")
    response_1 = conversational_rag_chain.invoke(
        input={"input": node + "的說明"},
        config={
            "configurable": {"session_id": session_id}
        }
    )
    STORE_DEFINITION[node] = response_1["answer"]
    
    


def _get_def(node):
    return STORE_DEFINITION[node]


def _get_customized_llm():
    return ChatOpenAI(model="gpt-3.5-turbo", temperature=0.0001)

def _get_retriever(pdf_path): 
    print(pdf_path)
    loader = PyPDFLoader(pdf_path)
    pages = loader.load_and_split()
        
    text = format_docs(pages)
    chunks = toChunks(text)
    embeddings = OpenAIEmbeddings()
    knowledge_base = FAISS.from_texts(chunks, embeddings)
    retriever = knowledge_base.as_retriever(
        search_kwargs={"k": 3}
    )
    
    return retriever

cc = opencc.OpenCC('s2twp')  # 將簡體中文轉換為繁體中文

def _get_retriever_whisper(pdf_path):
    
    #這是傳yt連結
    """
    print("下載中...！")
    yt = pt.YouTube("https://youtu.be/vsIsvcKA7M4?si=oeeMTeMarpyDCrkD")
    stream = yt.streams.filter(only_audio=True)[0]
    stream.download(filename="yt_audio.mp3")
    print("下載完成！")
    """
    
    print("whisper中...")
    model = whisper.load_model("base")

    result = model.transcribe(pdf_path)
    
    text = result["text"]
    text = cc.convert(text)
    #print(text)
    print(result)
    
    chunks = toChunks_whisper(text)
    print(chunks)
    embeddings = OpenAIEmbeddings()
    knowledge_base = FAISS.from_texts(chunks, embeddings)
    retriever = knowledge_base.as_retriever(
        search_kwargs={"k": 3}
    )
    
    return retriever, result

def _get_retriever_ocr(pdf_path):
    
    
    print("ocr中...")

    img = Image.open(pdf_path)
    result = pytesseract.image_to_string(img, lang='chi_tra')
    print(result)
    
    text = result
    text = cc.convert(text)
    print(text)
    
    
    chunks = toChunks_whisper(result)
    #print(chunks)
    embeddings = OpenAIEmbeddings()
    knowledge_base = FAISS.from_texts(chunks, embeddings)
    retriever = knowledge_base.as_retriever(
        search_kwargs={"k": 3}
    )
    
    return retriever

def _get_retriever_write(pdf_path):
    
    
    print("ocr中...")
    print(pdf_path)

    # convert to image using resolution 600 dpi 
    pages = convert_from_path(pdf_path, 600)

    # extract text
    text_data = ''
    for page in pages:
        text = pytesseract.image_to_string(page, lang='chi_tra')
        print(text)
        text_data += text + '\n'
    print(text_data)
    
    text = cc.convert(text_data)
    print(text)
    
    
    chunks = toChunks_whisper(text)
    #print(chunks)
    embeddings = OpenAIEmbeddings()
    knowledge_base = FAISS.from_texts(chunks, embeddings)
    retriever = knowledge_base.as_retriever(
        search_kwargs={"k": 3}
    )
    
    return retriever

def _get_retriever_yt(pdf_path):
    
    #這是傳yt連結
    
    print("下載中...！")
    #https://youtu.be/vsIsvcKA7M4?si=oeeMTeMarpyDCrkD
    yt = pt.YouTube(pdf_path)
    stream = yt.streams.filter(only_audio=True)[0]
    stream.download(filename="yt_audio.mp3")
    print("下載完成！")
    
    
    model = whisper.load_model("base")

    result = model.transcribe("yt_audio.mp3")
    text = result["text"]
    text = cc.convert(text)
    #print(text)
    print(result)
    
    chunks = toChunks_whisper(text)
    print(chunks)
    embeddings = OpenAIEmbeddings()
    knowledge_base = FAISS.from_texts(chunks, embeddings)
    retriever = knowledge_base.as_retriever(
        search_kwargs={"k": 3}
    )
    
    return retriever, result

#pdf to text
def format_docs(docs):
    return "\n\n".join([d.page_content for d in docs])
    
def toChunks(text):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,#500
        chunk_overlap=100,#100
        length_function=len,
    )
    return text_splitter.split_text(text)

def toChunks_whisper(text):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,#500
        chunk_overlap=100,#100
        length_function=len,
    )
    return text_splitter.split_text(text)

def init_node(llist, conversational_rag_chain, title, session_id):
    global front, reer
    print("====== conversation pass 1 ======")
    response_1 = conversational_rag_chain.invoke(
        input={"input": "摘要最重要的4~8個重點"},
        config={
            "configurable": {"session_id": session_id}
        }
    )
    answer = response_1["answer"]
    answer = cc.convert(answer)  
    print(answer) #print(response_1["answer"])

    print("====== conversation pass 2 ======")
    response_2 = conversational_rag_chain.invoke(
        input={"input": "條列式摘要其4~8個重點名詞作為標題"},
        config={
            "configurable": {"session_id": session_id}
        }
    )
    #print(response_2["context"])
    answer = response_2["answer"]
    answer = cc.convert(answer)  
    print(answer) #print(response_2["answer"])
    
    #-------------------------把你想要轉成ans的response放到這
    mkrespome = markdown.markdown(response_2["answer"])
    print(mkrespome)
    
    #加標題
    parent = llist.insertTitle(title)
    
    split = mkrespome.split("\n")
    #print(split[4])
    # 建立 c 個子執行緒
    threads = []       
    nodes = []
    c = 0
    for s in split:
        if s[1] == "l":
            #threads.append(threading.Thread(target = _store_def, args = (conversational_rag_chain, s[4:len(s)-5], session_id)))
            #threads[c].start()
            c+=1
            print("node " + str(c) + ":" + s[4:len(s)-5])
            nodes.append(s[4:len(s)-5])
            WORK.append(s[4:len(s)-5])
            WORK_THREAD.append(threading.Thread(target = gen_node, args = (llist, conversational_rag_chain, WORK[len(WORK)-1], session_id)))
            if front < 0:
                front += 1
            reer += 1
            #n.append(s[4:len(s)-5])
            #f.append(name)
            #e.append("##")
            #s[4:len(s)-5]
    print(nodes)
    
    llist.insertNode(parent, nodes, conversational_rag_chain, session_id)
    

    
@retry(wait=wait_random_exponential(multiplier=1, max=10))
def gen_node(llist, conversational_rag_chain, name, session_id):
    global front, reer
    print("====== conversation pass 1 ======")
    response_1 = conversational_rag_chain.invoke(
        input={"input": "摘要關於\"\"\"" + name + "\"\"\"內容中最重要的3~5個重點"},
        config={
            "configurable": {"session_id": session_id}
        }
    )
    answer = response_1["answer"]
    answer = cc.convert(answer)  
    print(answer) #print(response_1["answer"])

    print("====== conversation pass 2 ======")
    response_2 = conversational_rag_chain.invoke(
        input={"input": "條列式摘要以上3~5個重點名詞作為標題，但不包含\"\"\"" + name + "\"\"\"與之前所摘要過的重點名詞"},
        config={
            "configurable": {"session_id": session_id}
        }
    )
    answer = response_2["answer"]
    answer = cc.convert(answer)  
    print(answer) #print(response_2["answer"])

    mkrespome = markdown.markdown(response_2["answer"])
    print(mkrespome)
    
    parent = llist.searchParent(name)
    split = mkrespome.split("\n")
    
    nodes = []
    for s in split:
        if s.startswith("<li>"):
            node_name = s[4:len(s)-5]
            print("node: " + node_name)
            nodes.append(node_name)
            WORK.append(node_name)
            WORK_THREAD.append(threading.Thread(target = gen_node, args = (llist, conversational_rag_chain, node_name, session_id)))
            reer += 1

    print(nodes)
    
    llist.insertNode(parent, nodes, conversational_rag_chain, session_id)
    
def _clear_state():
    global STORE, STORE_DEFINITION, ANS, WORK, WORK_THREAD, DEFINITION_THREAD, STACK, front, reer, TSP
    STORE = dict()
    STORE_DEFINITION = dict()
    STACK = []
    ANS = []
    WORK = []
    WORK_THREAD = []
    DEFINITION_THREAD = []
    front = -1
    reer = -1   
    TSP = dict()
   
def generate(pdf_path, filename):
    global front, reer, WORK_THREAD, TSP
    _clear_state()  # 清除上次運行的狀態
    session_id = str(uuid.uuid4())  # 每次運行生成一個新的 session_id
    
    
    result = None
    knowledge_base_forTSP = None
    if pdf_path.split(".")[0] == 'OCR':
        print(pdf_path[4:])
        retriever = _get_retriever_write(pdf_path[4:])
    elif pdf_path.split(".")[1] == 'pdf':
        retriever = _get_retriever(pdf_path)
    elif pdf_path.split(".")[1] == 'mp3':
        retriever, result = _get_retriever_whisper(pdf_path)
    elif pdf_path.split(".")[1] == 'jpg' or pdf_path.split(".")[1] == 'png':
        retriever = _get_retriever_ocr(pdf_path)
    else:
        retriever, result = _get_retriever_yt(pdf_path)

    

    # 新加上的部分
    if result != None:
        print(len(result["segments"]))
        chunks = []
        for s in result["segments"]:
            chunks.append(s["text"])
            TSP[s["text"]] = s["start"]
        print(len(chunks))
        print(type(TSP))
        print(len(TSP))
        embeddings = OpenAIEmbeddings()
        knowledge_base_forTSP = FAISS.from_texts(chunks, embeddings)
        #docs = knowledge_base_forTSP.similarity_search(node)
        
    llm = _get_customized_llm()

    condense_prompt = ChatPromptTemplate.from_messages([
        ("system", CONDENSE_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")  
    ])

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", QA_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])


    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, condense_prompt
    )
    question_answer_chain = create_stuff_documents_chain(
        llm, qa_prompt
    )
    rag_chain = create_retrieval_chain(
        history_aware_retriever,
        question_answer_chain
    )


    conversational_rag_chain = RunnableWithMessageHistory(
        rag_chain,
        _get_memory,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer",
        config={"configurable": {"session_id": session_id}} 
    )
 
    llist = LinkedList()
    
    init_node(llist, conversational_rag_chain, filename, session_id)
    level = 3
    while level != 2 or front > reer:
        start = front
        end = reer
        fix = 16
        cur_start = start
        cur_stop = cur_start + fix
        while 1:
            if cur_start >= end + 1:
                break
            if cur_stop > end + 1:
                cur_stop = end + 1
            for i in range(cur_start, cur_stop):
                WORK_THREAD[i].start()
                front += 1
            for i in range(cur_start, cur_stop):
                WORK_THREAD[i].join()
            cur_start = cur_stop
            cur_stop = cur_start + fix
        level -= 1

    for i in range(len(DEFINITION_THREAD)):
        DEFINITION_THREAD[i].start()
    for i in range(len(DEFINITION_THREAD)):
        DEFINITION_THREAD[i].join()
    
    print("\n" + str(len(STORE_DEFINITION)))
    print(STORE_DEFINITION)

    llist.printLL(conversational_rag_chain, session_id, knowledge_base_forTSP) 
 

    print("\nfront:" + str(front))
    print("reer:" + str(reer))
    print("\nmarkdown:\n")
    for a in ANS:
        print(a)
        
    return "\n".join(ANS)