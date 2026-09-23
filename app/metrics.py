from prometheus_client import Counter, Histogram, Gauge, REGISTRY, generate_latest
import time

# Request counters
REQUESTS_TOTAL = Counter(
    "gateway_requests_total",
    "Total requests processed",
    ["tier", "cache_hit", "status"]  # status = "success" | "load_shed" | "error"
)

# Routing decision counter
ROUTING_DECISIONS = Counter(
    "gateway_routing_decisions_total",
    "Routing decisions by reason",
    ["tier", "reason"]
)

# LLM latency histogram
LLM_LATENCY = Histogram(
    "gateway_llm_latency_seconds",
    "End-to-end LLM call latency",
    ["tier", "model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Circuit breaker state gauge (1=closed, 0=open, 0.5=half_open)
CIRCUIT_BREAKER_STATE = Gauge(
    "gateway_circuit_breaker_state",
    "Circuit breaker state (1=closed, 0.5=half_open, 0=open)",
    ["model"]
)

# Active requests gauge
IN_FLIGHT_REQUESTS = Gauge(
    "gateway_in_flight_requests",
    "Number of currently in-flight LLM requests"
)

# Cache metrics
CACHE_HITS = Counter("gateway_semantic_cache_hits_total", "Semantic cache hits")
CACHE_MISSES = Counter("gateway_semantic_cache_misses_total", "Semantic cache misses")

# Coalescing metrics
COALESCED_REQUESTS = Counter("gateway_coalesced_requests_total", "Requests coalesced onto in-flight tasks")

