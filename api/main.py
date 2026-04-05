"""
FastAPI backend for StockBuddy (optional HTTP API).
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import uvicorn
from pathlib import Path
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from stockbuddy.graph.trading_graph import StockBuddyGraph
from stockbuddy.default_config import DEFAULT_CONFIG

app = FastAPI(
    title="StockBuddy API",
    description="Multi-Agent LLM Financial Trading Framework API",
    version="1.0.0"
)

# CORS 配置 - 允许移动端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境应该限制具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 存储分析任务状态
analysis_tasks = {}

# Pydantic Models
class AnalysisRequest(BaseModel):
    ticker: str
    analysis_date: str = datetime.now().strftime("%Y-%m-%d")
    analysts: List[str] = ["market", "social", "news", "fundamentals"]
    research_depth: int = 1
    llm_provider: str = "openai"
    quick_think_llm: str = "gpt-4o-mini"
    deep_think_llm: str = "gpt-4o-mini"

class AnalysisResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@app.get("/")
async def root():
    """健康检查端点"""
    return {
        "message": "StockBuddy API is running",
        "version": "1.0.0",
        "status": "healthy"
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/analyze", response_model=AnalysisResponse)
async def create_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """
    创建分析任务
    
    - **ticker**: 股票代码（如 AAPL, NVDA）
    - **analysis_date**: 分析日期 (YYYY-MM-DD)
    - **analysts**: 要使用的分析师列表
    - **research_depth**: 研究深度（辩论轮次）
    """
    task_id = f"{request.ticker}_{request.analysis_date}_{datetime.now().timestamp()}"
    
    # 验证日期格式
    try:
        analysis_date_obj = datetime.strptime(request.analysis_date, "%Y-%m-%d")
        if analysis_date_obj.date() > datetime.now().date():
            raise HTTPException(status_code=400, detail="Analysis date cannot be in the future")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # 初始化任务状态
    analysis_tasks[task_id] = {
        "status": "pending",
        "progress": {"current_agent": "initializing", "percentage": 0},
        "result": None,
        "error": None,
        "created_at": datetime.now().isoformat()
    }
    
    # 在后台运行分析
    background_tasks.add_task(run_analysis_task, task_id, request)
    
    return AnalysisResponse(
        task_id=task_id,
        status="pending",
        message=f"Analysis task created for {request.ticker}"
    )


async def run_analysis_task(task_id: str, request: AnalysisRequest):
    """后台运行分析任务"""
    try:
        # 更新状态为运行中
        analysis_tasks[task_id]["status"] = "running"
        analysis_tasks[task_id]["progress"]["current_agent"] = "initializing"
        analysis_tasks[task_id]["progress"]["percentage"] = 10
        
        # 创建配置
        config = DEFAULT_CONFIG.copy()
        config["max_debate_rounds"] = request.research_depth
        config["max_risk_discuss_rounds"] = request.research_depth
        config["quick_think_llm"] = request.quick_think_llm
        config["deep_think_llm"] = request.deep_think_llm
        config["llm_provider"] = request.llm_provider.lower()
        
        # 初始化图
        analysis_tasks[task_id]["progress"]["percentage"] = 20
        ta = StockBuddyGraph(
            selected_analysts=request.analysts,
            debug=False,
            config=config
        )
        
        # 运行分析
        analysis_tasks[task_id]["progress"]["current_agent"] = "analyzing"
        analysis_tasks[task_id]["progress"]["percentage"] = 40
        
        final_state, decision = ta.propagate(request.ticker, request.analysis_date)
        
        # 处理结果
        analysis_tasks[task_id]["progress"]["percentage"] = 90
        result = {
            "ticker": request.ticker,
            "analysis_date": request.analysis_date,
            "decision": decision,
            "market_report": final_state.get("market_report"),
            "sentiment_report": final_state.get("sentiment_report"),
            "news_report": final_state.get("news_report"),
            "fundamentals_report": final_state.get("fundamentals_report"),
            "investment_plan": final_state.get("investment_plan"),
            "trader_investment_plan": final_state.get("trader_investment_plan"),
            "final_trade_decision": final_state.get("final_trade_decision"),
            "completed_at": datetime.now().isoformat()
        }
        
        # 更新任务状态
        analysis_tasks[task_id]["status"] = "completed"
        analysis_tasks[task_id]["progress"]["percentage"] = 100
        analysis_tasks[task_id]["result"] = result
        
    except Exception as e:
        analysis_tasks[task_id]["status"] = "error"
        analysis_tasks[task_id]["error"] = str(e)
        analysis_tasks[task_id]["progress"]["percentage"] = 0


@app.get("/api/analysis/{task_id}", response_model=TaskStatus)
async def get_analysis_status(task_id: str):
    """获取分析任务状态"""
    if task_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = analysis_tasks[task_id]
    return TaskStatus(
        task_id=task_id,
        status=task_data["status"],
        progress=task_data["progress"],
        result=task_data["result"],
        error=task_data["error"]
    )


@app.get("/api/analysis/{task_id}/result")
async def get_analysis_result(task_id: str):
    """获取分析结果（仅当任务完成时）"""
    if task_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = analysis_tasks[task_id]
    
    if task_data["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Task is not completed yet. Current status: {task_data['status']}"
        )
    
    return task_data["result"]


@app.get("/api/tasks")
async def list_tasks():
    """列出所有分析任务"""
    return {
        "tasks": [
            {
                "task_id": task_id,
                "status": data["status"],
                "created_at": data["created_at"]
            }
            for task_id, data in analysis_tasks.items()
        ]
    }


@app.delete("/api/analysis/{task_id}")
async def delete_task(task_id: str):
    """删除分析任务"""
    if task_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    del analysis_tasks[task_id]
    return {"message": f"Task {task_id} deleted successfully"}


if __name__ == "__main__":
    # LAN IP for clients on same network
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print(f"\n{'='*60}")
    print(f"StockBuddy API Server Starting...")
    print(f"{'='*60}")
    print(f"Local access: http://localhost:8000")
    print(f"LAN access (same WiFi): http://{local_ip}:8000")
    print(f"API docs: http://localhost:8000/docs")
    print(f"{'='*60}\n")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # 开发模式自动重载
    )
