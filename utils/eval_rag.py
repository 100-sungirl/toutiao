"""RAG质量回归评测(RAGAS):
每次改动检索参数/换模型/改prompt后跑一次,对比各指标分数,证明"变好"有数字依据
指标: faithfulness(忠实度,幻觉的反面) / answer_relevancy(答案相关性)
      context_precision(检索精度,排前面的文档是否真相关) / context_recall(检索召回,该找到的都找到了吗)
用法: python utils/eval_rag.py  (结果存 results/ragas_report_{时间戳}.json)
"""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio,json,time
from datetime import datetime

import ragas
from ragas import evaluate,EvaluationDataset
from ragas.metrics import faithfulness,answer_relevancy,context_precision,context_recall
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.run_config import RunConfig

from services.rag_service import _retrieve_context,get_llm,get_embedding,RAG_SYSTEM_PROMPT,_format_docs
from langchain_core.messages import HumanMessage,SystemMessage

GOLDEN_SET = os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","tests","golden_set.json")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","results")

async def build_dataset(limit:int=14)->list:
    """对黄金集逐条执行完整RAG链路,组装ragas评测数据"""
    with open(GOLDEN_SET,encoding="utf-8") as f:
        golden = json.load(f)[:limit]
    llm = get_llm()
    samples = []
    for i,item in enumerate(golden,1):
        q = item["question"]
        docs = await _retrieve_context(q)  # 评测检索环节:含混合检索+Rerank
        contexts = [d.page_content for d in docs]
        resp = await llm.ainvoke([
            SystemMessage(content=RAG_SYSTEM_PROMPT.format(context=_format_docs(docs))),
            HumanMessage(content=q)])
        answer = resp.content if isinstance(resp.content,str) else str(resp.content)
        samples.append({"user_input":q,"response":answer,
                        "retrieved_contexts":contexts,"reference":item["reference"]})
        print(f"  [{i}/{len(golden)}] {q} -> 召回{len(contexts)}条")
    return samples

async def main():
    limit = int(sys.argv[1]) if len(sys.argv)>1 else 14
    print(f"== RAG质量评测(黄金集前{limit}条,ragas {ragas.__version__}) ==")
    t0 = time.time()
    samples = await build_dataset(limit)
    print(f"链路执行完成({int(time.time()-t0)}s),开始ragas指标计算...")
    dataset = EvaluationDataset.from_list(samples)
    result = evaluate(
        dataset,
        metrics=[faithfulness,answer_relevancy,context_precision,context_recall],
        llm=LangchainLLMWrapper(get_llm()),
        embeddings=LangchainEmbeddingsWrapper(get_embedding()),
        run_config=RunConfig(max_workers=4,max_wait=300,timeout=300),
        raise_exceptions=False,  # 单条失败记NaN不中断整体
    )
    # 取各指标均值(NaN的评测条目自动跳过)
    df = result.to_pandas()
    means = df[[m.name for m in [faithfulness,answer_relevancy,context_precision,context_recall]]].mean()
    scores = {m:round(float(v),4) for m,v in means.items() if v==v}
    report = {"timestamp":datetime.now().isoformat(timespec="seconds"),
              "samples":len(samples),"scores":scores}
    print("\n== 评测结果 ==")
    for m,v in scores.items():
        print(f"  {m}: {v}")
    print("  总评:",round(sum(scores.values())/len(scores),4) if scores else "NaN(全失败)")
    os.makedirs(RESULTS_DIR,exist_ok=True)
    out = os.path.join(RESULTS_DIR,f"ragas_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(out,"w",encoding="utf-8") as f:
        json.dump(report,f,ensure_ascii=False,indent=2)
    print(f"报告已保存: {out}")

if __name__ == "__main__":
    asyncio.run(main())
