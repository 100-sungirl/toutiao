"""LangGraph Agent:StateGraph实现ReAct循环,工具增强对话
流程: agent(LLM+bind_tools决策) --有工具调用--> tools(ToolNode执行) --> agent ... --无调用--> END
RAG检索(search_news)成为Agent的工具之一,由LLM按需决定是否检索,替代原固定"必检索"链路
"""
from typing import TypedDict,Optional,AsyncIterator,List,Dict,Any
from langchain_core.messages import SystemMessage,HumanMessage,AIMessage,AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph,START,END
from langgraph.prebuilt import ToolNode,tools_condition

from config.ai_config import AGENT_SYSTEM_PROMPT,CHAT_HISTORY_EXPIRE
from config.chat_cache import get_chat_history,set_chat_history
from crud.chat import save_chat_messages
from services.agent_tools import AGENT_TOOLS
from services.rag_service import get_llm,_truncate_history


class ChatState(TypedDict):
    """图状态:完整消息列表(含工具调用/工具结果消息)"""
    messages:List[AnyMessage]


_graph = None

def _history_to_messages(history:List[Dict[str,Any]],question:str)->List[AnyMessage]:
    """Redis dict历史 -> LangChain消息: system(人设+工具规范) + 历史 + 当前问题"""
    messages:List[AnyMessage] = [SystemMessage(content=AGENT_SYSTEM_PROMPT)]
    for item in history:
        if item["role"]=="user":
            messages.append(HumanMessage(content=item["content"]))
        elif item["role"]=="assistant":
            messages.append(AIMessage(content=item["content"]))
    messages.append(HumanMessage(content=question))
    return messages

def get_graph():
    """单例编译LangGraph: agent <-> tools 循环"""
    global _graph
    if _graph is None:
        llm = get_llm().bind_tools(AGENT_TOOLS)

        async def call_agent(state:ChatState):
            return {"messages":[await llm.ainvoke(state["messages"])]}

        g = StateGraph(ChatState)
        g.add_node("agent",call_agent)
        g.add_node("tools",ToolNode(AGENT_TOOLS))
        g.add_edge(START,"agent")
        # LLM输出含tool_calls则去tools节点,否则结束
        g.add_conditional_edges("agent",tools_condition,["tools",END])
        g.add_edge("tools","agent")
        _graph = g.compile()
    return _graph

def _make_config(user_id:int,sources_collector:list)->RunnableConfig:
    """经config向工具注入用户上下文与来源收集器(工具内可读写)"""
    return RunnableConfig(configurable={"user_id":user_id,"sources_collector":sources_collector})

def _dedupe_sources(sources:List[Dict[str,Any]])->List[Dict[str,Any]]:
    """按news_id去重(多轮工具调用可能召回重复新闻)"""
    seen,out = set(),[]
    for s in sources:
        nid = s.get("news_id")
        if nid is not None and nid in seen:
            continue
        seen.add(nid)
        out.append(s)
    return out

async def _persist(user_id:int,question:str,reply:str,sources:List[Dict[str,Any]],session_id:Optional[int])->None:
    """完成后写Redis热历史+MySQL持久化(与原链路一致)"""
    history = await get_chat_history(user_id)
    history.append({"role":"user","content":question})
    history.append({"role":"assistant","content":reply})
    history = _truncate_history(history)
    await set_chat_history(user_id,history,expire=CHAT_HISTORY_EXPIRE)
    await save_chat_messages(user_id,question,reply,sources,session_id=session_id)

async def run_chat(user_id:int,question:str,session_id:Optional[int]=None)->Dict[str,Any]:
    """非流式Agent对话:返回{reply,sources}"""
    history = await get_chat_history(user_id)
    collector:List[Dict[str,Any]] = []
    state = {"messages":_history_to_messages(history,question)}
    result = await get_graph().ainvoke(state,config=_make_config(user_id,collector))
    last = result["messages"][-1]
    reply = last.content if isinstance(last.content,str) else str(last.content)
    sources = _dedupe_sources(collector)
    await _persist(user_id,question,reply,sources,session_id)
    return {"reply":reply,"sources":sources}

async def run_chat_stream(user_id:int,question:str,session_id:Optional[int]=None)->AsyncIterator[Dict[str,Any]]:
    """流式Agent对话:astream_events提取token,产出 sources -> content* -> done 事件(SSE协议不变)
    过滤条件:只透传agent节点的模型token,工具内部的LLM调用(改写/多查询)不外漏
    """
    history = await get_chat_history(user_id)
    collector:List[Dict[str,Any]] = []
    config = _make_config(user_id,collector)
    state = {"messages":_history_to_messages(history,question)}

    sent_sources = False
    reply_parts:List[str] = []
    async for ev in get_graph().astream_events(state,config=config,version="v2"):
        kind = ev.get("event")
        if kind=="on_chat_model_stream" and (ev.get("metadata") or {}).get("langgraph_node")=="agent":
            chunk = ev["data"]["chunk"]
            text = chunk.content if isinstance(getattr(chunk,"content",None),str) else ""
            if text:
                reply_parts.append(text)
                yield {"type":"content","data":text}
        elif kind=="on_tool_end":# 工具执行完,引用来源已进收集器,推送前端渲染
            ss = _dedupe_sources(collector)
            if ss and not sent_sources:
                sent_sources = True
                yield {"type":"sources","data":ss}

    reply = "".join(reply_parts)
    sources = _dedupe_sources(collector)
    if sources and not sent_sources:# 兜底:工具事件漏发时在结尾补
        yield {"type":"sources","data":sources}
    await _persist(user_id,question,reply,sources,session_id)
    yield {"type":"done","data":None}
