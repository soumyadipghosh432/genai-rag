"""
Health Check API Endpoints
===========================

FastAPI endpoints for monitoring application health including
database connectivity, LLM services, and tool availability.
"""

import logging
import time
from typing import Dict, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from ..dependencies import (
    check_database_health,
    check_llm_health,
    check_tools_health,
    get_app_settings,
    get_request_id
)
from ..config import Settings

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthStatus(BaseModel):
    """Health status model"""
    status: str
    message: str
    timestamp: str
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "message": "Service is operational",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


class DetailedHealthStatus(BaseModel):
    """Detailed health status with component breakdown"""
    overall_status: str
    components: Dict[str, HealthStatus]
    uptime_seconds: float
    version: str
    environment: str
    request_id: str
    
    class Config:
        schema_extra = {
            "example": {
                "overall_status": "healthy",
                "components": {
                    "database": {
                        "status": "healthy",
                        "message": "Database connection successful",
                        "timestamp": "2024-01-15T10:30:00Z"
                    },
                    "llm": {
                        "status": "healthy", 
                        "message": "LLM provider (amazon_nova) is available",
                        "timestamp": "2024-01-15T10:30:00Z"
                    },
                    "tools": {
                        "status": "healthy",
                        "message": "Tools system operational",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                },
                "uptime_seconds": 3600.5,
                "version": "1.0.0",
                "environment": "development",
                "request_id": "req_12345"
            }
        }


# Track application start time for uptime calculation
_start_time = time.time()


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Basic health check",
    description="Simple health check endpoint for load balancers and basic monitoring",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Service is healthy"},
        503: {"description": "Service is unhealthy"}
    }
)
async def health_check(
    request_id: str = Depends(get_request_id)
) -> HealthStatus:
    """
    Basic health check endpoint.
    
    Returns simple health status for load balancers and basic monitoring.
    This endpoint should be fast and lightweight.
    """
    
    try:
        logger.debug(f"Health check request - Request ID: {request_id}")
        
        return HealthStatus(
            status="healthy",
            message="AI Chatbot service is operational",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        
    except Exception as e:
        logger.error(f"Health check failed - Request ID: {request_id} - Error: {str(e)}")
        return HealthStatus(
            status="unhealthy",
            message=f"Health check failed: {str(e)}",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )


@router.get(
    "/health/detailed",
    response_model=DetailedHealthStatus,
    summary="Detailed health check",
    description="Comprehensive health check with component status breakdown",
    responses={
        200: {"description": "Detailed health status"},
        503: {"description": "One or more components are unhealthy"}
    }
)
async def detailed_health_check(
    db_health: Dict[str, Any] = Depends(check_database_health),
    llm_health: Dict[str, Any] = Depends(check_llm_health),
    tools_health: Dict[str, Any] = Depends(check_tools_health),
    settings: Settings = Depends(get_app_settings),
    request_id: str = Depends(get_request_id)
) -> DetailedHealthStatus:
    """
    Detailed health check endpoint.
    
    Checks all system components including:
    - Database connectivity
    - LLM service availability
    - Tools system status
    """
    
    try:
        logger.info(f"Detailed health check request - Request ID: {request_id}")
        
        # Convert health check results to HealthStatus models
        components = {
            "database": HealthStatus(**db_health),
            "llm": HealthStatus(**llm_health),
            "tools": HealthStatus(**tools_health)
        }
        
        # Determine overall status
        unhealthy_components = [
            name for name, health in components.items()
            if health.status != "healthy"
        ]
        
        overall_status = "unhealthy" if unhealthy_components else "healthy"
        
        if unhealthy_components:
            logger.warning(f"Unhealthy components detected: {unhealthy_components}")
        
        # Calculate uptime
        uptime_seconds = time.time() - _start_time
        
        return DetailedHealthStatus(
            overall_status=overall_status,
            components=components,
            uptime_seconds=round(uptime_seconds, 2),
            version=settings.app_version,
            environment=settings.environment,
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"Detailed health check failed - Request ID: {request_id} - Error: {str(e)}")
        
        # Return unhealthy status with error information
        error_health = HealthStatus(
            status="unhealthy",
            message=f"Health check error: {str(e)}",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        
        return DetailedHealthStatus(
            overall_status="unhealthy",
            components={
                "database": error_health,
                "llm": error_health,
                "tools": error_health
            },
            uptime_seconds=round(time.time() - _start_time, 2),
            version=getattr(settings, 'app_version', '1.0.0'),
            environment=getattr(settings, 'environment', 'unknown'),
            request_id=request_id
        )


@router.get(
    "/health/database",
    response_model=HealthStatus,
    summary="Database health check",
    description="Check database connectivity and status",
    responses={
        200: {"description": "Database is healthy"},
        503: {"description": "Database is unhealthy"}
    }
)
async def database_health_check(
    db_health: Dict[str, Any] = Depends(check_database_health),
    request_id: str = Depends(get_request_id)
) -> HealthStatus:
    """Check database health specifically"""
    
    logger.info(f"Database health check - Request ID: {request_id}")
    return HealthStatus(**db_health)


@router.get(
    "/health/llm", 
    response_model=HealthStatus,
    summary="LLM service health check",
    description="Check LLM service availability and configuration",
    responses={
        200: {"description": "LLM service is healthy"},
        503: {"description": "LLM service is unhealthy"}
    }
)
async def llm_health_check(
    llm_health: Dict[str, Any] = Depends(check_llm_health),
    request_id: str = Depends(get_request_id)
) -> HealthStatus:
    """Check LLM service health specifically"""
    
    logger.info(f"LLM health check - Request ID: {request_id}")
    return HealthStatus(**llm_health)


@router.get(
    "/health/tools",
    response_model=HealthStatus,
    summary="Tools system health check", 
    description="Check tools system availability and registered tools",
    responses={
        200: {"description": "Tools system is healthy"},
        503: {"description": "Tools system is unhealthy"}
    }
)
async def tools_health_check(
    tools_health: Dict[str, Any] = Depends(check_tools_health),
    request_id: str = Depends(get_request_id)
) -> HealthStatus:
    """Check tools system health specifically"""
    
    logger.info(f"Tools health check - Request ID: {request_id}")
    return HealthStatus(**tools_health)


@router.get(
    "/health/readiness",
    response_model=HealthStatus,
    summary="Readiness probe",
    description="Kubernetes-style readiness probe to check if service is ready to accept traffic",
    responses={
        200: {"description": "Service is ready"},
        503: {"description": "Service is not ready"}
    }
)
async def readiness_probe(
    db_health: Dict[str, Any] = Depends(check_database_health),
    llm_health: Dict[str, Any] = Depends(check_llm_health),
    settings: Settings = Depends(get_app_settings),
    request_id: str = Depends(get_request_id)
) -> HealthStatus:
    """
    Readiness probe for Kubernetes deployments.
    
    Checks critical components that must be available before
    the service can accept traffic.
    """
    
    logger.debug(f"Readiness probe - Request ID: {request_id}")
    
    try:
        # Check critical components
        critical_checks = [db_health, llm_health]
        
        all_healthy = all(
            check.get("status") == "healthy" 
            for check in critical_checks
        )
        
        if all_healthy:
            return HealthStatus(
                status="healthy",
                message="Service is ready to accept traffic",
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )
        else:
            unhealthy_components = [
                "database" if db_health.get("status") != "healthy" else None,
                "llm" if llm_health.get("status") != "healthy" else None
            ]
            unhealthy_components = [c for c in unhealthy_components if c]
            
            return HealthStatus(
                status="unhealthy",
                message=f"Service not ready - unhealthy components: {', '.join(unhealthy_components)}",
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )
            
    except Exception as e:
        logger.error(f"Readiness probe failed - Request ID: {request_id} - Error: {str(e)}")
        return HealthStatus(
            status="unhealthy",
            message=f"Readiness check failed: {str(e)}",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )


@router.get(
    "/health/liveness",
    response_model=HealthStatus,
    summary="Liveness probe",
    description="Kubernetes-style liveness probe to check if service is alive",
    responses={
        200: {"description": "Service is alive"},
        503: {"description": "Service is not responding"}
    }
)
async def liveness_probe(
    request_id: str = Depends(get_request_id)
) -> HealthStatus:
    """
    Liveness probe for Kubernetes deployments.
    
    Simple check to verify the service is alive and responding.
    Should not perform heavy operations.
    """
    
    logger.debug(f"Liveness probe - Request ID: {request_id}")
    
    try:
        return HealthStatus(
            status="healthy",
            message="Service is alive and responding",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        
    except Exception as e:
        logger.error(f"Liveness probe failed - Request ID: {request_id} - Error: {str(e)}")
        return HealthStatus(
            status="unhealthy",
            message=f"Liveness check failed: {str(e)}",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )