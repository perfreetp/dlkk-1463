from fastapi import APIRouter
from . import auth, examination, quality_rule, anomaly, review, statistics, benchmark, scheduler

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证授权"])
api_router.include_router(examination.router, prefix="/examinations", tags=["检查数据"])
api_router.include_router(quality_rule.router, prefix="/rules", tags=["规则管理"])
api_router.include_router(anomaly.router, prefix="/anomalies", tags=["异常管理"])
api_router.include_router(review.router, prefix="/review", tags=["复核流转"])
api_router.include_router(statistics.router, prefix="/statistics", tags=["统计报送"])
api_router.include_router(benchmark.router, prefix="/benchmark", tags=["院区对标"])
api_router.include_router(scheduler.router, prefix="/scheduler", tags=["任务调度"])
