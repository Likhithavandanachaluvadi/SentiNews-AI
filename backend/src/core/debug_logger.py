"""
Structured Debug Logging for LangGraph Agents.
Provides comprehensive execution visibility across all nodes.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class NodeStatus(str, Enum):
    """Node execution status."""
    STARTED = "started"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class NodeExecutionLog:
    """Structured log entry for a single node execution."""
    node_name: str
    status: NodeStatus
    timestamp: str
    execution_ms: int
    input_state: Dict[str, Any]
    output_state: Dict[str, Any]
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # Node-specific metrics
    missing_fields: List[str] = None
    validation_errors: List[str] = None
    citations_count: int = 0
    confidence_score: Optional[float] = None
    retrieval_sources: List[str] = None
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class DebugLogger:
    """Centralized debug logger for the entire research pipeline."""
    
    def __init__(self):
        self.logs: List[NodeExecutionLog] = []
        self.execution_start = None
    
    def start_execution(self):
        """Mark the start of a complete workflow execution."""
        self.execution_start = datetime.utcnow()
        self.logs = []
        logger.info("=== RESEARCH WORKFLOW STARTED ===")
    
    def log_node_execution(
        self,
        node_name: str,
        status: NodeStatus,
        input_state: Dict[str, Any],
        output_state: Dict[str, Any],
        execution_ms: int,
        error_message: Optional[str] = None,
        retry_count: int = 0,
        missing_fields: Optional[List[str]] = None,
        validation_errors: Optional[List[str]] = None,
        citations_count: int = 0,
        confidence_score: Optional[float] = None,
        retrieval_sources: Optional[List[str]] = None,
    ) -> NodeExecutionLog:
        """
        Log a single node execution with full context.
        
        Args:
            node_name: Name of the node
            status: Execution status (started, success, failed, partial, skipped)
            input_state: Input state dict
            output_state: Output state dict
            execution_ms: Execution time in milliseconds
            error_message: Error message if failed
            retry_count: Number of retries performed
            missing_fields: Fields missing from retrieval/analysis
            validation_errors: Validation errors detected
            citations_count: Number of citations/sources
            confidence_score: Confidence score (0-100 or 0.0-1.0)
            retrieval_sources: List of retrieved sources
        
        Returns:
            NodeExecutionLog object
        """
        log_entry = NodeExecutionLog(
            node_name=node_name,
            status=status,
            timestamp=datetime.utcnow().isoformat(),
            execution_ms=execution_ms,
            input_state=input_state,
            output_state=output_state,
            error_message=error_message,
            retry_count=retry_count,
            missing_fields=missing_fields or [],
            validation_errors=validation_errors or [],
            citations_count=citations_count,
            confidence_score=confidence_score,
            retrieval_sources=retrieval_sources or [],
        )
        
        self.logs.append(log_entry)
        
        # Log to standard logger
        log_dict = log_entry.to_dict()
        logger.info(
            f"NODE EXECUTION: {node_name} | Status: {status} | "
            f"Time: {execution_ms}ms | Confidence: {confidence_score} | "
            f"Citations: {citations_count}"
        )
        if error_message:
            logger.warning(f"  Error: {error_message}")
        if missing_fields:
            logger.warning(f"  Missing Fields: {', '.join(missing_fields)}")
        
        return log_entry
    
    def log_intent_classification(
        self,
        query: str,
        primary_intent: str,
        secondary_intent: Optional[str],
        intent_confidence: float,
        query_risk_level: str,
        complexity_level: str,
        extracted_ticker: Optional[str],
        reasoning: str,
    ):
        """Log intent classification results."""
        logger.info(
            f"INTENT CLASSIFICATION:\n"
            f"  Query: {query}\n"
            f"  Primary Intent: {primary_intent}\n"
            f"  Secondary Intent: {secondary_intent}\n"
            f"  Confidence: {intent_confidence:.2f}\n"
            f"  Risk Level: {query_risk_level}\n"
            f"  Complexity: {complexity_level}\n"
            f"  Ticker: {extracted_ticker}\n"
            f"  Reasoning: {reasoning}"
        )
    
    def log_retrieval_operation(
        self,
        ticker: str,
        intent: str,
        sources_retrieved: int,
        data_types: List[str],
        execution_ms: int,
        filtered_sources: Optional[List[str]] = None,
        blocked_sources: Optional[List[str]] = None,
    ):
        """Log retrieval operation details."""
        logger.info(
            f"RETRIEVAL OPERATION:\n"
            f"  Ticker: {ticker}\n"
            f"  Intent: {intent}\n"
            f"  Sources Retrieved: {sources_retrieved}\n"
            f"  Data Types: {', '.join(data_types)}\n"
            f"  Execution Time: {execution_ms}ms"
        )
        if filtered_sources:
            logger.info(f"  Filtered Sources: {', '.join(filtered_sources[:5])}")
        if blocked_sources:
            logger.warning(f"  Blocked Sources: {', '.join(blocked_sources[:5])}")
    
    def log_state_propagation(
        self,
        node_name: str,
        state_keys_before: Dict[str, Any],
        state_keys_after: Dict[str, Any],
        null_overwrites: Optional[List[str]] = None,
    ):
        """Log state changes to detect null propagation issues."""
        logger.info(f"STATE PROPAGATION: {node_name}")
        
        # Check for null overwrites
        if null_overwrites:
            logger.error(
                f"  ⚠️ NULL OVERWRITES DETECTED: {', '.join(null_overwrites)}\n"
                f"  Valid state was overwritten with null!"
            )
        
        # Log added/modified keys
        for key in state_keys_after:
            if key not in state_keys_before:
                logger.debug(f"  + Added: {key}")
            elif state_keys_before[key] != state_keys_after[key]:
                logger.debug(f"  ~ Modified: {key}")
    
    def log_verifier_feedback(
        self,
        is_valid: bool,
        contradictions: List[str],
        hallucinations: List[str],
        sebi_violations: List[str],
        feedback: str,
    ):
        """Log verifier results."""
        status_icon = "✓" if is_valid else "✗"
        logger.info(
            f"VERIFIER OUTPUT: {status_icon}\n"
            f"  Valid: {is_valid}\n"
            f"  Contradictions Found: {len(contradictions)}\n"
            f"  Hallucinations Detected: {len(hallucinations)}\n"
            f"  SEBI Violations: {len(sebi_violations)}\n"
            f"  Feedback: {feedback}"
        )
        if contradictions:
            logger.warning(f"  Contradictions: {contradictions[:3]}")
        if hallucinations:
            logger.warning(f"  Hallucinations: {hallucinations[:3]}")
        if sebi_violations:
            logger.error(f"  SEBI Violations: {sebi_violations}")
    
    def log_synthesis_result(
        self,
        outlook_label: str,
        conviction_level: str,
        overall_confidence: int,
        sections_populated: List[str],
        sections_missing: List[str],
        synthesis_quality: str,
    ):
        """Log Judge synthesis results."""
        logger.info(
            f"SYNTHESIS RESULT:\n"
            f"  Outlook: {outlook_label}\n"
            f"  Conviction: {conviction_level}\n"
            f"  Overall Confidence: {overall_confidence}%\n"
            f"  Populated Sections: {', '.join(sections_populated)}\n"
            f"  Missing Sections: {', '.join(sections_missing) if sections_missing else 'None'}\n"
            f"  Quality: {synthesis_quality}"
        )
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Generate a summary of the entire workflow execution."""
        if not self.execution_start:
            return {"error": "No execution has been logged yet"}
        
        total_time = (datetime.utcnow() - self.execution_start).total_seconds() * 1000
        
        summary = {
            "total_execution_ms": total_time,
            "node_count": len(self.logs),
            "successful_nodes": sum(1 for log in self.logs if log.status == NodeStatus.SUCCESS),
            "failed_nodes": sum(1 for log in self.logs if log.status == NodeStatus.FAILED),
            "partial_nodes": sum(1 for log in self.logs if log.status == NodeStatus.PARTIAL),
            "total_citations": sum(log.citations_count for log in self.logs),
            "average_confidence": (
                sum(log.confidence_score for log in self.logs if log.confidence_score is not None)
                / max(1, sum(1 for log in self.logs if log.confidence_score is not None))
            ),
            "nodes": [log.to_dict() for log in self.logs],
        }
        
        logger.info(
            f"=== WORKFLOW EXECUTION SUMMARY ===\n"
            f"Total Time: {total_time:.0f}ms\n"
            f"Nodes: {len(self.logs)} | Success: {summary['successful_nodes']} | "
            f"Failed: {summary['failed_nodes']} | Partial: {summary['partial_nodes']}\n"
            f"Average Confidence: {summary['average_confidence']:.1f}%"
        )
        
        return summary
    
    def get_logs_json(self) -> str:
        """Export logs as JSON for debugging UI."""
        summary = self.get_execution_summary()
        return json.dumps(summary, indent=2, default=str)


# Global instance
debug_logger = DebugLogger()


def start_workflow_logging():
    """Start a new workflow execution session."""
    debug_logger.start_execution()


def get_debug_summary() -> Dict[str, Any]:
    """Get the current execution summary."""
    return debug_logger.get_execution_summary()
