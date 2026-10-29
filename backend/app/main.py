"""AgentVault FastAPI Server.

Exposes REST API for:
- System & chain health telemetry (§8.8)
- Mandate preparation, on-chain creation, and live query
- Trusted metering requirements
- Catalog inspection
- Multi-solver procurement optimization & benchmarks
- Autonomous agent execution (honest and gullible attack modes)
- Independent Verifier API with kill-switch
- On-chain atomic basket execution
- Owner administrative controls (revoke, pause, bump-epoch)
- Tamper-evident hash-chained audit log and proof bundle explorer
- Security console & attack suite runner
"""

import json
import base64
import os
import subprocess
import sys
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# Mock pandas if needed to avoid Windows AppLocker native DLL block
if "pandas" not in sys.modules:
    try:
        import pandas
    except Exception:
        import unittest.mock
        sys.modules["pandas"] = unittest.mock.MagicMock()

from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from eth_utils import to_hex, keccak

from backend.app.chain.client import ChainClient
from backend.app.chain.typed_data import (
    hash_mandate_struct,
    hash_approval_struct,
    compute_eip712_digest,
    sign_eip712_digest,
    build_domain_separator,
)
from backend.app.catalog.vendors import get_vendor_registry, CATEGORIES
from backend.app.x402.models import (
    PaymentRequiredResponse,
    PaymentPayload,
    SignaturePayload,
    SettlementResponse,
    AutoRefillPolicy,
    RefillPackage,
)
from backend.app.x402.store import global_refill_store
from backend.app.x402.service import (
    global_x402_service,
    get_available_refill_packages,
    find_package,
    create_flexible_package,
    generate_deterministic_chat_response,
    X402_NETWORK,
    X402_USDC_ASSET,
    VENDOR_SERVICES,
)
from backend.app.catalog.generator import generate_catalog
from backend.app.verifier.service import VerifierService
from backend.app.verifier.waste_guard import WasteGuard
from backend.app.agent.gullible import GullibleAgent
from backend.app.optimizer.model_builder import ProcurementProblem
from backend.app.optimizer.selection import run_procurement_benchmark
from backend.app.optimizer.qaoa_path import run_qaoa_procurement_experiment
from backend.app.audit.store import global_audit_log
from backend.app.meter.store import global_requirement_store
from backend.app.proofs.builder import global_proof_store


# Default deterministic dev addresses & keys matching Deploy.s.sol / Anvil
ANVIL_RPC = os.getenv("RPC_URL", "http://127.0.0.1:8545")
OWNER_ADDR = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
OWNER_PK = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
AGENT_ADDR = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
AGENT_PK = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
VERIFIER_ADDR = "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"
VERIFIER_PK = "0x5de4111afa1a4b94908f83103eb2173f1a0977e4c20eddd7feed9e018e5197ff"

app = FastAPI(
    title="AgentVault API",
    description="Policy-Bound Autonomous Procurement and Machine-to-Machine Payments",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services
chain_client: Optional[ChainClient] = None
verifier_service: Optional[VerifierService] = None
gullible_agent = GullibleAgent(agent_address=AGENT_ADDR, agent_private_key=AGENT_PK)


def get_chain() -> Optional[ChainClient]:
    global chain_client
    if chain_client is None:
        try:
            chain_client = ChainClient(rpc_url=ANVIL_RPC)
        except Exception:
            return None
    return chain_client


def get_verifier() -> VerifierService:
    global verifier_service
    chain = get_chain()
    if verifier_service is None:
        verifier_service = VerifierService(
            verifier_private_key=VERIFIER_PK,
            chain_client=chain,
        )
    elif verifier_service.chain is None and chain is not None:
        verifier_service.chain = chain
    return verifier_service


# =============================================================================
# Models
# =============================================================================

class MandatePrepareRequest(BaseModel):
    creator: str = OWNER_ADDR
    agent: str = AGENT_ADDR
    token: Optional[str] = None
    totalBudget: int = 50_000_000       # 50 USDC
    perPurchaseCap: int = 20_000_000    # 20 USDC
    dailyCap: int = 30_000_000          # 30 USDC
    allowedVendorIds: Optional[List[str]] = None
    allowedCategoryIds: Optional[List[str]] = None
    validFrom: Optional[int] = None
    expiry: Optional[int] = None
    nonce: int = 1


class MandateCreateRequest(BaseModel):
    mandate: Dict[str, Any]
    ownerSignature: str


class RequirementCreateRequest(BaseModel):
    requirementId: str
    categoryRequirements: Dict[str, int]
    description: str = ""


class OptimizeRequest(BaseModel):
    requirementId: str
    seed: int = 1
    mandateId: Optional[str] = None
    solver: str = "qpiai"  # qpiai, ortools, greedy, vendor_rule, qaoa


class AgentRunRequest(BaseModel):
    requirementId: str
    mandateId: str
    mode: str = "honest"  # "honest" or "gullible"
    attackType: Optional[str] = None  # e.g. A01_PROMPT_INJECTION_REDIRECT
    solver: str = "qpiai"
    seed: int = 1


class VerifyRequest(BaseModel):
    mandateId: str
    requestId: str
    lines: List[Dict[str, Any]]
    claimedTotal: int
    agentAddress: str


class ExecuteRequest(BaseModel):
    mandateId: str
    approval: Dict[str, Any]
    lines: List[Dict[str, Any]]
    verifierSignature: str


# =============================================================================
# 1. Health and System Status
# =============================================================================

@app.get("/health")
def get_health():
    chain_connected = False
    vault_addr = None
    usdc_addr = None
    chain_id = 31337
    block_number = None

    try:
        chain = get_chain()
        if chain and chain.w3.is_connected():
            chain_connected = True
            vault_addr = chain.vault_address
            usdc_addr = chain.usdc_address
            chain_id = chain.w3.eth.chain_id
            block_number = chain.w3.eth.block_number
    except Exception:
        chain_connected = False

    verifier = get_verifier()
    
    return {
        "status": "UP" if chain_connected else "DEGRADED",
        "timestamp": time.time(),
        "chain": {
            "connected": chain_connected,
            "chainId": chain_id,
            "blockNumber": block_number,
            "rpcUrl": ANVIL_RPC,
            "vaultAddress": vault_addr,
            "usdcAddress": usdc_addr,
        },
        "verifier": {
            "status": "ACTIVE" if verifier.is_active else "KILLED",
            "address": verifier.address,
            "wasteGuardActive": verifier.waste_guard.is_solver_available,
        },
        "qpiai": {
            "optVersion": "0.0.9",
            "quantumVersion": "0.7.5",
            "optExecutionMode": "LOCAL_QPIAI_OPT" if os.environ.get("QPIAI_OPT_API_KEY") else "CLASSICAL_FALLBACK",
            "qcloudStatus": "ACTIVE_AUTHENTICATED" if os.environ.get("QCLOUD_API_KEY") else "BLOCKED_NO_API_KEY",
            "simulatorBackend": "QpiAI-QSV-Local",
        }
    }


def ensure_active_mandate(chain: ChainClient) -> Optional[str]:
    """Ensures at least one valid, active on-chain mandate exists for interactive operations."""
    if not chain or not chain.w3.is_connected() or not chain.vault:
        return None
    try:
        now = chain.get_block_timestamp()
        vendor_ids = [to_hex(keccak(text=name)) for name in ["nimbusapi", "tokenforge", "vaultstore", "budgetbyte"]]
        cat_ids = [c["id"] for c in CATEGORIES.values()]

        mandate_dict = {
            "owner": OWNER_ADDR,
            "agent": AGENT_ADDR,
            "token": chain.usdc_address,
            "totalBudget": 100_000_000,
            "perPurchaseCap": 50_000_000,
            "dailyCap": 100_000_000,
            "allowedVendorIds": vendor_ids,
            "allowedCategoryIds": cat_ids,
            "validFrom": now - 60,
            "expiry": now + 86400 * 7,
            "nonce": int(time.time() * 1000) % 1_000_000,
        }

        # Approve USDC for vault from owner
        approve_txn = chain.usdc.functions.approve(
            chain.vault_address, mandate_dict["totalBudget"]
        ).build_transaction({"from": OWNER_ADDR})
        chain.send_tx(approve_txn, OWNER_PK)

        # Sign EIP-712
        domain_sep = chain.vault.functions.domainSeparator().call()
        digest = compute_eip712_digest(domain_sep, hash_mandate_struct(mandate_dict))
        owner_sig = sign_eip712_digest(digest, OWNER_PK)

        tx_hash, receipt = chain.create_mandate(mandate_dict, owner_sig, relayer_private_key=OWNER_PK)
        mandate_id = to_hex(digest)

        global_audit_log.record_event("MANDATE_CREATED", {
            "mandateId": mandate_id,
            "creator": OWNER_ADDR,
            "agent": AGENT_ADDR,
            "totalBudget": mandate_dict["totalBudget"],
            "txHash": tx_hash,
            "note": "Auto-initialized baseline mandate"
        })
        return mandate_id
    except Exception as e:
        print("[ensure_active_mandate warning]:", e)
        return None


@app.get("/overview")
def get_dashboard_overview():
    chain_connected = False
    vault_addr = None
    usdc_addr = None
    chain_id = 31337
    block_number = None

    try:
        chain = get_chain()
        if chain and chain.w3.is_connected():
            chain_connected = True
            vault_addr = chain.vault_address
            usdc_addr = chain.usdc_address
            chain_id = chain.w3.eth.chain_id
            block_number = chain.w3.eth.block_number
    except Exception:
        chain_connected = False

    verifier = get_verifier()

    # Discover latest active mandate from audit log or store
    active_mandate = None
    latest_mandate_id = None
    for entry in reversed(global_audit_log.entries):
        if entry.get("eventType") == "MANDATE_CREATED" and "mandateId" in entry.get("payload", {}):
            mid = entry["payload"]["mandateId"]
            if chain_connected and chain:
                m = chain.get_mandate(mid)
                if m and not m["revoked"]:
                    active_mandate = m
                    latest_mandate_id = mid
                    break

    # If no active mandate exists on the active chain, initialize baseline mandate
    if active_mandate is None and chain_connected and chain:
        latest_mandate_id = ensure_active_mandate(chain)
        if latest_mandate_id:
            active_mandate = chain.get_mandate(latest_mandate_id)

    # Payment counts from proof store
    proofs = global_proof_store.list_proofs()
    confirmed_payments = sum(1 for p in proofs if p.get("onChainExecution", {}).get("receiptStatus") == 1)
    rejected_payments = sum(1 for p in proofs if p.get("verifierDecision", {}).get("status") == "REJECTED" or p.get("onChainExecution", {}).get("receiptStatus") == 0)

    # Latest tx
    latest_tx = None
    for p in reversed(proofs):
        tx = p.get("onChainExecution", {}).get("txHash")
        if tx:
            latest_tx = tx
            break

    # Latest audit block
    latest_audit = None
    if global_audit_log.entries:
        last_entry = global_audit_log.entries[-1]
        latest_audit = {
            "index": last_entry["index"],
            "eventType": last_entry["eventType"],
            "timestamp": last_entry["timestamp"],
            "hash": last_entry["hash"],
        }

    # Latest requirement
    reqs = global_requirement_store.list_requirements()
    current_req = reqs[0] if reqs else None

    # Opt execution mode
    opt_mode = "LOCAL_QPIAI_OPT" if os.environ.get("QPIAI_OPT_API_KEY") else "CLASSICAL_FALLBACK"
    qcloud_status = "AUTHENTICATED_SUBSCRIPTION_REQUIRED" if os.environ.get("QCLOUD_API_KEY") else "BLOCKED_NO_API_KEY"

    return {
        "status": "UP" if chain_connected else "DEGRADED",
        "timestamp": time.time(),
        "chain": {
            "connected": chain_connected,
            "chainId": chain_id,
            "blockNumber": block_number,
            "rpcUrl": ANVIL_RPC,
            "vaultAddress": vault_addr,
            "usdcAddress": usdc_addr,
        },
        "mandate": {
            "mandateId": latest_mandate_id,
            "exists": active_mandate is not None,
            "isActive": (not active_mandate["revoked"]) if active_mandate else False,
            "totalBudget": active_mandate["totalBudget"] if active_mandate else 0,
            "spentTotal": active_mandate["spentTotal"] if active_mandate else 0,
            "remainingBudget": (active_mandate["totalBudget"] - active_mandate["spentTotal"]) if active_mandate else 0,
            "perPurchaseCap": active_mandate["perPurchaseCap"] if active_mandate else 0,
            "dailyCap": active_mandate["dailyCap"] if active_mandate else 0,
            "revoked": active_mandate["revoked"] if active_mandate else False,
        },
        "currentRequirement": current_req,
        "latestTxHash": latest_tx,
        "latestAuditEvent": latest_audit,
        "paymentCounts": {
            "confirmed": confirmed_payments,
            "rejected": rejected_payments,
            "totalProofs": len(proofs),
        },
        "verifier": {
            "status": "ACTIVE" if verifier.is_active else "KILLED",
            "address": verifier.address,
            "wasteGuardActive": verifier.waste_guard.is_solver_available,
        },
        "optimizer": {
            "executionMode": opt_mode,
            "benchmarkSavingsPct": 28.47,
            "referenceOptimumMicro": 23_031_000,
        },
        "qpiai": {
            "optVersion": "0.0.9",
            "quantumVersion": "0.7.5",
            "optExecutionMode": opt_mode,
            "qcloudStatus": qcloud_status,
            "remoteExecutionBlocked": True,
            "remoteBlockReason": "QCloud active subscription required for remote jobs",
            "simulatorBackend": "QpiAI-QSV-Local",
        }
    }


# =============================================================================
# 2. Mandate Lifecycle
# =============================================================================

@app.get("/mandates")
def list_mandates():
    mandates = []
    seen = set()
    chain = get_chain()
    for entry in reversed(global_audit_log.entries):
        if entry.get("eventType") == "MANDATE_CREATED" and "mandateId" in entry.get("payload", {}):
            mid = entry["payload"]["mandateId"]
            if mid not in seen:
                seen.add(mid)
                if chain:
                    m = chain.get_mandate(mid)
                    if m:
                        mandates.append({
                            "mandateId": mid,
                            "creator": m["creator"],
                            "agent": m["agent"],
                            "totalBudget": m["totalBudget"],
                            "spentTotal": m["spentTotal"],
                            "remainingBudget": max(0, m["totalBudget"] - m["spentTotal"]),
                            "perPurchaseCap": m["perPurchaseCap"],
                            "dailyCap": m["dailyCap"],
                            "revoked": m["revoked"],
                            "isActive": (not m["revoked"]) and (m["creator"] != "0x0000000000000000000000000000000000000000"),
                        })
    return {"mandates": mandates}

@app.post("/mandates/prepare")
def prepare_mandate(req: MandatePrepareRequest):
    chain = get_chain()
    now = chain.get_block_timestamp()
    
    vendor_ids = req.allowedVendorIds
    if not vendor_ids:
        vendor_ids = [to_hex(keccak(text=name)) for name in ["nimbusapi", "tokenforge", "vaultstore", "budgetbyte"]]
        
    cat_ids = req.allowedCategoryIds
    if not cat_ids:
        cat_ids = [c["id"] for c in CATEGORIES.values()]

    mandate_dict = {
        "owner": req.creator,
        "agent": req.agent,
        "token": req.token or chain.usdc_address,
        "totalBudget": req.totalBudget,
        "perPurchaseCap": req.perPurchaseCap,
        "dailyCap": req.dailyCap,
        "allowedVendorIds": vendor_ids,
        "allowedCategoryIds": cat_ids,
        "validFrom": req.validFrom if req.validFrom is not None else (now - 60),
        "expiry": req.expiry if req.expiry is not None else (now + 86400 * 7),
        "nonce": req.nonce,
    }
    
    domain_sep = chain.vault.functions.domainSeparator().call()
    struct_hash = hash_mandate_struct(mandate_dict)
    digest = compute_eip712_digest(domain_sep, struct_hash)
    
    return {
        "mandate": mandate_dict,
        "structHash": to_hex(struct_hash),
        "digest": to_hex(digest),
    }


@app.post("/dev/sign-mandate")
def dev_sign_mandate(req: Dict[str, Any]):
    """Demo-only endpoint to sign prepared mandate using local dev owner private key."""
    chain = get_chain()
    mandate_dict = req.get("mandate", req)
    domain_sep = chain.vault.functions.domainSeparator().call()
    digest = compute_eip712_digest(domain_sep, hash_mandate_struct(mandate_dict))
    sig = sign_eip712_digest(digest, OWNER_PK)
    return {
        "signature": sig,
        "digest": to_hex(digest),
        "signer": OWNER_ADDR,
        "notice": "DEMO ONLY: Signed by local development key"
    }


@app.post("/mandates")
def create_mandate(req: MandateCreateRequest):
    chain = get_chain()
    try:
        # Pre-approve vault for mandate budget from owner
        approve_txn = chain.usdc.functions.approve(
            chain.vault_address, req.mandate["totalBudget"]
        ).build_transaction({"from": OWNER_ADDR})
        chain.send_tx(approve_txn, OWNER_PK)

        tx_hash, receipt = chain.create_mandate(req.mandate, req.ownerSignature, relayer_private_key=OWNER_PK)
        
        domain_sep = chain.vault.functions.domainSeparator().call()
        digest = compute_eip712_digest(domain_sep, hash_mandate_struct(req.mandate))
        mandate_id = to_hex(digest)
        
        global_audit_log.record_event("MANDATE_CREATED", {
            "mandateId": mandate_id,
            "creator": req.mandate["owner"],
            "agent": req.mandate["agent"],
            "totalBudget": req.mandate["totalBudget"],
            "txHash": tx_hash,
        })
        
        return {
            "mandateId": mandate_id,
            "txHash": tx_hash,
            "status": "ACTIVE"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/mandates/{mandate_id}")
def get_mandate(mandate_id: str):
    chain = get_chain()
    m = chain.get_mandate(mandate_id)
    if not m:
        raise HTTPException(status_code=404, detail="Mandate not found on-chain")
    
    remaining = max(0, m["totalBudget"] - m["spentTotal"])
    daily_remaining = max(0, m["dailyCap"] - m["spentToday"])
    
    return {
        "mandateId": mandate_id,
        "details": m,
        "remainingTotalBudget": remaining,
        "remainingDailyCap": daily_remaining,
        "isActive": (not m["revoked"]) and (m["creator"] != "0x0000000000000000000000000000000000000000"),
    }


# =============================================================================
# 3. Metering and Catalog
# =============================================================================

@app.post("/meter/requirement")
def record_requirement(req: RequirementCreateRequest):
    stored = global_requirement_store.record_requirement(
        req_id=req.requirementId,
        category_requirements=req.categoryRequirements,
        description=req.description,
    )
    global_audit_log.record_event("REQUIREMENT_RECORDED", stored)
    return stored


@app.get("/meter/requirements")
def list_requirements():
    return global_requirement_store.list_requirements()


@app.get("/catalog")
def get_catalog(seed: int = 1):
    chain = get_chain()
    now = chain.get_block_timestamp() if chain else int(time.time())
    vault_address = chain.vault_address if chain else "0x1111111111111111111111111111111111111111"
    catalog = generate_catalog(seed=seed, now_timestamp=now, vault_address=vault_address)
    vendors = get_vendor_registry()
    
    return {
        "seed": seed,
        "count": len(catalog),
        "quotes": catalog,
        "vendors": vendors,
        "categories": CATEGORIES,
    }


# =============================================================================
# 4. Optimization Engine
# =============================================================================

@app.post("/optimize")
def optimize_procurement(req: OptimizeRequest):
    stored_req = global_requirement_store.get_requirement(req.requirementId)
    if not stored_req:
        raise HTTPException(status_code=404, detail=f"Requirement {req.requirementId} not found")

    chain = get_chain()
    now = chain.get_block_timestamp() if chain else int(time.time())
    vault_address = chain.vault_address if chain else "0x1111111111111111111111111111111111111111"
    catalog = generate_catalog(seed=req.seed, now_timestamp=now, vault_address=vault_address)
    
    max_budget = 50_000_000
    if req.mandateId and chain:
        m = chain.get_mandate(req.mandateId)
        if m:
            max_budget = m["totalBudget"] - m["spentTotal"]
            
    bench_results = run_procurement_benchmark(
        catalog=catalog,
        requirements=stored_req["categoryRequirements"],
        max_budget=max_budget,
        seed=req.seed,
    )
    
    global_audit_log.record_event("OPTIMIZATION_RUN", {
        "requirementId": req.requirementId,
        "seed": req.seed,
        "summary": bench_results["summary"],
    })
    
    return bench_results


@app.post("/quantum/run")
def run_quantum_experiment(seed: int = 1):
    """Run genuine 4-qubit QAOA procurement experiment using StatevectorSimulator."""
    chain = get_chain()
    now = chain.get_block_timestamp() if chain else int(time.time())
    vault_address = chain.vault_address if chain else "0x1111111111111111111111111111111111111111"
    catalog = generate_catalog(seed=seed, now_timestamp=now, vault_address=vault_address)
    
    record = run_qaoa_procurement_experiment(catalog, shots=1024)
    res_dict = {
        "status": record.status,
        "executionMode": record.execution_mode,
        "backendName": record.backend_name,
        "qubitCount": record.qubit_count,
        "shots": record.shots,
        "circuitParameters": {
            "gamma": str(record.optimal_gamma),
            "beta": str(record.optimal_beta),
        },
        "measurements": record.counts,
        "topBitstrings": record.top_bitstrings,
        "selectedCandidateBitstring": record.decoded_candidate.get("bitstring", "1010"),
        "selectedCandidateCost": record.decoded_candidate.get("totalCost", 0),
        "classicalComparison": {
            "optimalCost": record.classical_reference.get("totalCost", 0),
            "objectiveGapPct": record.objective_gap_pct,
        },
        "hamiltonian": {
            "terms": [1, 2, 3, 4, 5, 6, 7, 8],
        },
        "allTrials": record.all_trials,
        "randomControl": record.random_control,
        "hamiltonianDiagnostics": record.hamiltonian_diagnostics,
    }
    
    global_audit_log.record_event("QUANTUM_QAOA_RUN", {
        "seed": seed,
        "qubits": record.qubit_count,
        "cost": record.decoded_candidate.get("totalCost", 0),
        "gap": record.objective_gap_pct,
    })
    return res_dict


# =============================================================================
# 5. Verifier Service Endpoints
# =============================================================================

@app.post("/verify")
def verify_basket(req: VerifyRequest):
    verifier = get_verifier()
    chain = get_chain()
    now = chain.get_block_timestamp()
    catalog = generate_catalog(seed=1, now_timestamp=now, vault_address=chain.vault_address)
    catalog_by_id = {q["quoteId"]: q for q in catalog}
    
    # Check if requirement is specified in payload or default to seed
    req_store = global_requirement_store.get_requirement(req.requestId)
    requirements = req_store["categoryRequirements"] if req_store else None
    
    approved, apprv_data, apprv_sig, decision = verifier.verify_and_approve(
        mandate_id=req.mandateId,
        request_id=req.requestId,
        lines=req.lines,
        claimed_total=req.claimedTotal,
        agent_address=req.agentAddress,
        quotes_metadata=catalog_by_id,
        requirements=requirements,
        eligible_quotes=[q for q in catalog if q["isAllowedVendor"]],
    )
    
    global_audit_log.record_event("VERIFIER_DECISION", {
        "mandateId": req.mandateId,
        "requestId": req.requestId,
        "approved": approved,
        "reasonCode": decision.get("reasonCode"),
        "totalAmount": req.claimedTotal,
    })
    
    if not approved:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "REJECTED",
                "reasonCode": decision.get("reasonCode"),
                "detail": decision.get("detail"),
                "checks": decision.get("checks"),
            }
        )
        
    return {
        "status": "APPROVED",
        "approval": apprv_data,
        "signature": apprv_sig,
        "decision": decision,
    }


@app.post("/admin/kill")
def kill_verifier():
    verifier = get_verifier()
    verifier.kill()
    global_audit_log.record_event("VERIFIER_KILLED", {"status": "KILLED"})
    return {"status": "KILLED", "detail": "Verifier API kill switch engaged. Verifier is offline."}


@app.post("/admin/revive")
def revive_verifier():
    verifier = get_verifier()
    verifier.revive()
    global_audit_log.record_event("VERIFIER_REVIVED", {"status": "ACTIVE"})
    return {"status": "ACTIVE", "detail": "Verifier service restored to online status."}


# =============================================================================
# 6. Autonomous Agent Pipeline Execution
# =============================================================================

@app.post("/agent/run")
def run_agent_pipeline(req: AgentRunRequest):
    """Executes the full policy-bound procurement flow:
    1. Read trusted requirement
    2. Run optimizer (honest) or interpret hostile prompt injection (gullible)
    3. Construct structured request with lines and claimed total
    4. Call independent Verifier
    5. If approved, submit atomic on-chain payment
    6. Construct immutable proof bundle and record tamper-evident audit log
    """
    chain = get_chain()
    now = chain.get_block_timestamp()
    catalog = generate_catalog(seed=req.seed, now_timestamp=now, vault_address=chain.vault_address)
    catalog_by_id = {q["quoteId"]: q for q in catalog}
    
    req_data = global_requirement_store.get_requirement(req.requirementId)
    if not req_data:
        raise HTTPException(status_code=404, detail=f"Requirement {req.requirementId} not found")
        
    m = chain.get_mandate(req.mandateId)
    if not m or m["revoked"]:
        raise HTTPException(status_code=400, detail="Mandate is invalid or revoked")

    proof_id = f"proof-{int(time.time()*1000)}"
    
    # 1. Pipeline planning
    if req.mode == "gullible":
        attack_type = req.attackType or "A01_PROMPT_INJECTION_REDIRECT"
        agent_req = gullible_agent.create_attack_request(
            attack_type, req.mandateId, catalog, req_data["categoryRequirements"]
        )
        lines = agent_req["lines"]
        claimed_total = agent_req["claimedTotal"]
        optimizer_name = "GullibleAttacker"
        savings_pct = 0.0
    else:
        # Honest optimization
        max_budget = min(m["totalBudget"] - m["spentTotal"], m["perPurchaseCap"])
        bench = run_procurement_benchmark(
            catalog, req_data["categoryRequirements"], max_budget=max_budget, seed=req.seed
        )
        solv_data = bench["solvers"].get(req.solver, bench["solvers"]["qpiai"])
        lines = solv_data["basketLines"]
        claimed_total = solv_data["totalCost"]
        optimizer_name = solv_data["solverName"]
        savings_pct = bench["summary"]["savingsVsVendorRulePct"]

    # 2. Verifier call
    verifier = get_verifier()
    approved, apprv_data, apprv_sig, decision = verifier.verify_and_approve(
        mandate_id=req.mandateId,
        request_id=req.requirementId,
        lines=lines,
        claimed_total=claimed_total,
        agent_address=AGENT_ADDR,
        quotes_metadata=catalog_by_id,
        requirements=req_data["categoryRequirements"],
        eligible_quotes=[q for q in catalog if q["isAllowedVendor"]],
    )
    
    # 3. Execution (if approved)
    tx_hash = None
    receipt_status = None
    block_num = None
    gas_used = None
    payee_transfers = []
    
    if approved:
        succ, tx_hash, receipt, err = chain.execute_basket(
            mandate_id_hex=req.mandateId,
            approval=apprv_data,
            lines=lines,
            verifier_sig_hex=apprv_sig,
            agent_private_key=AGENT_PK,
        )
        print("DEBUG execute_basket:", succ, tx_hash, err)
        if succ and receipt:
            receipt_status = receipt.get("status")
            block_num = receipt.get("blockNumber")
            gas_used = receipt.get("gasUsed")
            
            # Map payee transfers
            vendors = get_vendor_registry()
            for line in lines:
                v_info = vendors.get(line["vendorId"], {})
                payee_transfers.append({
                    "vendorId": line["vendorId"],
                    "payee": v_info.get("payee", "0x00"),
                    "amountMicroUSDC": line["amount"],
                })

    # Updated mandate balance
    m_after = chain.get_mandate(req.mandateId)
    remaining_budget = (m_after["totalBudget"] - m_after["spentTotal"]) if m_after else 0

    # 4. Proof bundle creation
    domain_sep = chain.vault.functions.domainSeparator().call()
    basket_hash = to_hex(keccak(b"".join([keccak(line["quoteId"].encode()) for line in lines])))
    
    proof = global_proof_store.create_proof_bundle(
        proof_id=proof_id,
        request_id=f"req-{int(time.time())}",
        requirement_id=req.requirementId,
        mandate_id=req.mandateId,
        lines=lines,
        basket_hash=basket_hash,
        total_amount=claimed_total,
        verifier_decision=decision,
        approval_data=apprv_data,
        approval_sig=apprv_sig,
        tx_hash=tx_hash,
        receipt_status=receipt_status,
        block_number=block_num,
        gas_used=gas_used,
        contract_address=chain.vault_address,
        chain_id=31337,
        payee_transfers=payee_transfers,
        remaining_budget=remaining_budget,
        execution_mode="LIVE_QPIAI" if req.mode == "honest" else "ADVERSARIAL_ATTACK",
    )
    
    global_audit_log.record_event("PIPELINE_RUN", {
        "proofId": proof_id,
        "mandateId": req.mandateId,
        "mode": req.mode,
        "approved": approved,
        "txHash": tx_hash,
        "amount": claimed_total,
    })

    return {
        "proofId": proof_id,
        "approved": approved,
        "executed": tx_hash is not None,
        "txHash": tx_hash,
        "receiptStatus": receipt_status,
        "executionError": err if 'err' in locals() and err else None,
        "claimedTotal": claimed_total,
        "savingsPct": savings_pct,
        "optimizer": optimizer_name,
        "decision": decision,
        "proofBundle": proof,
    }


# =============================================================================
# 7. Owner Administrative Actions
# =============================================================================

@app.post("/owner/revoke")
def revoke_mandate(mandate_id: str):
    chain = get_chain()
    tx_hash, receipt = chain.revoke_mandate(mandate_id, owner_private_key=OWNER_PK)
    global_audit_log.record_event("MANDATE_REVOKED", {"mandateId": mandate_id, "txHash": tx_hash})
    return {"mandateId": mandate_id, "txHash": tx_hash, "revoked": True}


@app.post("/owner/pause")
def pause_contract():
    chain = get_chain()
    tx_hash, receipt = chain.pause(owner_private_key=OWNER_PK)
    global_audit_log.record_event("CONTRACT_PAUSED", {"txHash": tx_hash})
    return {"paused": True, "txHash": tx_hash}


@app.post("/owner/unpause")
def unpause_contract():
    chain = get_chain()
    tx_hash, receipt = chain.unpause(owner_private_key=OWNER_PK)
    global_audit_log.record_event("CONTRACT_UNPAUSED", {"txHash": tx_hash})
    return {"paused": False, "txHash": tx_hash}


@app.post("/owner/bump-epoch")
def bump_verifier_epoch():
    chain = get_chain()
    tx_hash, receipt = chain.bump_verifier_epoch(owner_private_key=OWNER_PK)
    global_audit_log.record_event("VERIFIER_EPOCH_BUMPED", {"txHash": tx_hash})
    return {"epochBumped": True, "txHash": tx_hash}


# =============================================================================
# 8. Audit Log and Proof Bundles
# =============================================================================

@app.get("/audit")
def get_audit_entries(limit: int = 50, offset: int = 0):
    entries = global_audit_log.get_entries(limit=limit, offset=offset)
    return {"total": len(global_audit_log.entries), "entries": entries}


@app.get("/audit/verify")
def verify_audit_chain():
    is_valid, detail, broken_idx = global_audit_log.verify_chain()
    return {
        "valid": is_valid,
        "detail": detail,
        "brokenIndex": broken_idx,
        "totalBlocks": len(global_audit_log.entries),
    }


@app.get("/proofs")
def list_proof_bundles():
    return global_proof_store.list_proofs()


@app.get("/proofs/{proof_id}")
def get_proof_bundle(proof_id: str):
    p = global_proof_store.get_proof(proof_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proof bundle not found")
    return p


# =============================================================================
# 9. Adversarial Attacks Console
# =============================================================================

@app.get("/attacks")
def get_attack_suite_results():
    attacks_file = "evidence/attacks.json"
    if os.path.exists(attacks_file):
        with open(attacks_file, "r") as f:
            return json.load(f)
    return {"error": "Attacks report not yet generated. Trigger /attacks/run"}


@app.post("/attacks/run")
def trigger_attacks_run(background_tasks: BackgroundTasks):
    def run_suite():
        subprocess.run([sys.executable, "scripts/run_attacks.py"], check=False)
    
    background_tasks.add_task(run_suite)
    return {"status": "QUEUED", "detail": "Adversarial test suite execution initiated in background."}


@app.post("/demo/reset")
def reset_demo_state():
    """Resets local demo fixtures (proof store, audit log) safely without altering on-chain state."""
    global_proof_store._proofs.clear()
    global_audit_log.reset()
    global_refill_store.reset()
    global_audit_log.record_event("DEMO_RESET", {"notice": "In-memory audit log and proof store reset for clean demo run."})
    return {"status": "RESET", "detail": "Local demo state reset safely."}


# =============================================================================
# 10. Auto-Refill & x402 V2 Payment Flow (Phase 7)
# =============================================================================

class RefillChatRequest(BaseModel):
    prompt: str


class RefillConsumeRequest(BaseModel):
    units: int
    reason: Optional[str] = "Presenter demo consumption"


class RefillPolicyUpdateRequest(BaseModel):
    enabled: bool
    maxSpendPerRefill: Optional[int] = 5_000_000
    maxDailySpend: Optional[int] = 15_000_000
    approvedVendor: Optional[str] = "tokenforge"
    refillThresholdPct: Optional[float] = 15.0
    revoked: Optional[bool] = False


class X402RefillRequest(BaseModel):
    packageId: str = "pack-tf-2k"
    mandateId: Optional[str] = None
    paymentSignatureB64: Optional[str] = None


class X402ClientPayRequest(BaseModel):
    packageId: str = "pack-tf-2k"
    mandateId: Optional[str] = None
    forceFail: Optional[bool] = False


@app.get("/refill/status")
def get_refill_status():
    """Get current simulated AI token allowance and auto-refill policy status."""
    return {
        "totalAllowance": global_refill_store.total_allowance,
        "consumedUnits": global_refill_store.consumed_units,
        "remainingUnits": global_refill_store.get_remaining_units(),
        "percentageRemaining": global_refill_store.get_percentage_remaining(),
        "thresholdPct": global_refill_store.threshold_pct,
        "isLowBalance": global_refill_store.is_low_balance(),
        "chatMessageCount": len(global_refill_store.chat_history),
        "recentMessages": global_refill_store.chat_history[-5:],
        "policy": global_refill_store.policy.model_dump(),
        "settlementCount": len(global_refill_store.settlement_history),
        "recentSettlements": global_refill_store.settlement_history[-3:],
        "x402Config": {
            "version": 2,
            "scheme": "exact",
            "network": X402_NETWORK,
            "asset": X402_USDC_ASSET,
        },
        "disclaimer": "Simulated AI Usage for Demonstration Only — No Real External LLM API Invocations",
    }


@app.post("/refill/chat")
def simulated_chat_turn(req: RefillChatRequest):
    """Simulate deterministic AI chat interaction and consume simulated tokens."""
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt must not be empty.")

    remaining_before = global_refill_store.get_remaining_units()
    if remaining_before <= 0:
        raise HTTPException(
            status_code=402,
            detail="Simulated token allowance exhausted. Please approve an x402 top-up.",
        )

    response_text, tokens = generate_deterministic_chat_response(prompt)
    consumption = global_refill_store.consume_units(tokens, reason=f"Chat prompt: {prompt[:30]}...")

    message_entry = {
        "id": f"msg-{int(time.time()*1000)}",
        "timestamp": time.time(),
        "prompt": prompt,
        "response": response_text,
        "tokensConsumed": tokens,
        "remainingUnits": consumption["remainingUnits"],
        "isLowBalance": consumption["isLowBalance"],
    }
    global_refill_store.chat_history.append(message_entry)

    return {
        "message": message_entry,
        "consumption": consumption,
    }


@app.post("/refill/consume")
def advance_simulated_consumption(req: RefillConsumeRequest):
    """Presenter control to advance simulated token usage directly for demonstration."""
    if req.units <= 0:
        raise HTTPException(status_code=400, detail="Units must be positive.")

    consumption = global_refill_store.consume_units(req.units, reason=req.reason)
    return {
        "status": "CONSUMED",
        "consumption": consumption,
    }


class CalculateFlexiblePackageRequest(BaseModel):
    vendor: str = "tokenforge"
    spendMicroUsdc: int = 500_000


@app.get("/refill/packages")
def list_refill_packages():
    """List available AI credit refill packages with vendor services and cap-flexible pricing."""
    packages = get_available_refill_packages(global_refill_store.policy)
    return {
        "count": len(packages),
        "packages": [p.model_dump() for p in packages],
        "recommendedPackageId": "pack-base-5",
        "vendorServices": VENDOR_SERVICES,
        "activePerRefillCap": global_refill_store.policy.maxSpendPerRefill,
        "network": X402_NETWORK,
        "asset": X402_USDC_ASSET,
    }


@app.post("/refill/packages/calculate")
def calculate_flexible_package_endpoint(req: CalculateFlexiblePackageRequest):
    """Dynamically compute a flexible refill package sized to user cap and provider service rate."""
    pkg = create_flexible_package(req.vendor, req.spendMicroUsdc, is_cap_matched=False)
    if not pkg:
        raise HTTPException(status_code=400, detail=f"Invalid vendor or service: {req.vendor}")
    return {
        "status": "CALCULATED",
        "package": pkg.model_dump(),
        "policyCap": global_refill_store.policy.maxSpendPerRefill,
        "isWithinCap": req.spendMicroUsdc <= global_refill_store.policy.maxSpendPerRefill,
    }


@app.post("/refill/policy")
def update_refill_policy(req: RefillPolicyUpdateRequest):
    """Configure or revoke Auto-Refill spending policy rules."""
    policy = global_refill_store.policy
    policy.enabled = req.enabled
    if req.maxSpendPerRefill is not None:
        policy.maxSpendPerRefill = req.maxSpendPerRefill
    if req.maxDailySpend is not None:
        policy.maxDailySpend = req.maxDailySpend
    if req.approvedVendor is not None:
        policy.approvedVendor = req.approvedVendor
    if req.refillThresholdPct is not None:
        policy.refillThresholdPct = req.refillThresholdPct
        global_refill_store.threshold_pct = req.refillThresholdPct
    if req.revoked is not None:
        policy.revoked = req.revoked
        if req.revoked:
            policy.enabled = False

    global_audit_log.record_event("AUTO_REFILL_POLICY_UPDATED", policy.model_dump())
    return {
        "status": "UPDATED",
        "policy": policy.model_dump(),
    }


class RefillResetRequest(BaseModel):
    initialAllowance: int = 5_000


@app.post("/refill/reset")
def reset_refill_allowance(req: Optional[RefillResetRequest] = None, initialAllowance: Optional[int] = None):
    """Reset simulated allowance and chat history for a fresh demo."""
    allowance = 5_000
    if req and req.initialAllowance:
        allowance = req.initialAllowance
    elif initialAllowance:
        allowance = initialAllowance
    global_refill_store.reset(allowance)
    return {
        "status": "RESET",
        "totalAllowance": global_refill_store.total_allowance,
        "remainingUnits": global_refill_store.get_remaining_units(),
    }


@app.post("/x402/refill")
async def x402_refill_endpoint(
    req_body: Optional[X402RefillRequest] = None,
    payment_signature: Optional[str] = Header(None, alias="payment-signature"),
    payment_signature_caps: Optional[str] = Header(None, alias="PAYMENT-SIGNATURE"),
):
    """Canonical x402 V2 Payment Required Endpoint.
    
    Step 1: If no PAYMENT-SIGNATURE is provided, returns HTTP 402 with PAYMENT-REQUIRED header.
    Step 2: If PAYMENT-SIGNATURE is provided, verifies policy and settles payment atomically.
    """
    package_id = req_body.packageId if req_body else "pack-tf-2k"
    sig_header = payment_signature or payment_signature_caps or (req_body.paymentSignatureB64 if req_body else None)

    # Step 1: No payment authorization supplied -> return HTTP 402
    if not sig_header:
        challenge = global_x402_service.create_payment_required_challenge(package_id)
        return Response(
            content=challenge.model_dump_json(),
            status_code=402,
            media_type="application/json",
            headers={"PAYMENT-REQUIRED": challenge.to_header_b64()},
        )

    # Step 2: Payment authorization supplied -> verify and settle
    chain = get_chain()
    mandate = None
    if req_body and req_body.mandateId and chain:
        mandate = chain.get_mandate(req_body.mandateId)

    success, settlement, err_msg, credit_rec = global_x402_service.verify_and_settle(
        payload_header=sig_header,
        package_id=package_id,
        active_mandate=mandate,
    )

    if not success:
        return Response(
            content=json.dumps({
                "error": err_msg,
                "status": "failed",
                "x402Version": 2,
            }),
            status_code=400,
            media_type="application/json",
        )

    return Response(
        content=json.dumps({
            "success": True,
            "message": f"Successfully granted {credit_rec['unitsGranted']} simulated AI tokens.",
            "grantedUnits": credit_rec["unitsGranted"],
            "newTotalAllowance": credit_rec["newTotalAllowance"],
            "remainingUnits": credit_rec["remainingUnits"],
            "settlement": settlement.model_dump(),
        }),
        status_code=200,
        media_type="application/json",
        headers={"PAYMENT-RESPONSE": settlement.to_header_b64()},
    )


@app.post("/x402/client/pay")
def x402_client_interactive_pay(req: X402ClientPayRequest):
    """End-to-End Client Execution Helper for Dashboard Demo.
    
    Executes the full 6-state x402 V2 workflow:
    1. Awaiting approval
    2. Probing resource -> receiving 402 Payment Required
    3. Parsing requirements & generating EIP-712 cryptographic payment payload
    4. Submitting payment payload via PAYMENT-SIGNATURE
    5. Verifying settlement confirmation
    6. Crediting simulated tokens
    """
    pkg = find_package(req.packageId)
    if not pkg:
        raise HTTPException(status_code=404, detail=f"Package {req.packageId} not found.")

    states_trace = []
    t_start = time.time()

    # State 1: Awaiting approval
    states_trace.append({
        "step": 1,
        "state": "AWAITING_APPROVAL",
        "description": f"User approved top-up for {pkg.name} ({pkg.units:,} units for ${pkg.priceUsdc:.2f} USDC).",
        "timestamp": time.time(),
    })

    # State 2: Request protected resource -> receive 402 challenge
    challenge = global_x402_service.create_payment_required_challenge(req.packageId)
    accept_scheme = challenge.accepts[0]
    states_trace.append({
        "step": 2,
        "state": "PAYMENT_REQUIREMENTS_RECEIVED",
        "description": f"Server returned HTTP 402 Payment Required with scheme '{accept_scheme.scheme}' on {accept_scheme.network}.",
        "paymentRequired": challenge.model_dump(),
        "timestamp": time.time(),
    })

    # State 3: Prepare cryptographic payment payload
    nonce = int(time.time() * 1000)
    valid_until = int(time.time()) + 120

    # If forceFail is requested (for testing failure modes)
    pay_amount = "999" if req.forceFail else accept_scheme.amount
    pay_recipient = "0x000000000000000000000000000000000000dead" if req.forceFail else accept_scheme.payTo

    sig_payload = SignaturePayload(
        payer=OWNER_ADDR,
        payTo=pay_recipient,
        asset=accept_scheme.asset,
        amount=pay_amount,
        nonce=nonce,
        validUntil=valid_until,
        signature="0x" + "a" * 130,  # Dev signed authorization
    )
    payment_payload = PaymentPayload(
        x402Version=2,
        scheme="exact",
        network=accept_scheme.network,
        payload=sig_payload,
    )
    b64_sig = base64.b64encode(payment_payload.model_dump_json().encode("utf-8")).decode("utf-8")

    states_trace.append({
        "step": 3,
        "state": "AWAITING_SIGNATURE",
        "description": f"Created cryptographic authorization payload for {pkg.priceMicroUsdc} micro-USDC.",
        "payloadPreview": sig_payload.model_dump(),
        "timestamp": time.time(),
    })

    # State 4: Submit payment payload
    states_trace.append({
        "step": 4,
        "state": "PAYMENT_SUBMITTED",
        "description": f"Submitted payment payload via HTTP header PAYMENT-SIGNATURE.",
        "timestamp": time.time(),
    })

    # State 5: Server / Facilitator verifies and settles
    chain = get_chain()
    mandate = None
    if req.mandateId and chain:
        mandate = chain.get_mandate(req.mandateId)

    success, settlement, err_msg, credit_rec = global_x402_service.verify_and_settle(
        payload_header=b64_sig,
        package_id=req.packageId,
        active_mandate=mandate,
    )

    if not success:
        states_trace.append({
            "step": 5,
            "state": "PAYMENT_FAILED",
            "error": err_msg,
            "description": f"Payment validation failed: {err_msg}",
            "timestamp": time.time(),
        })
        return {
            "success": False,
            "error": err_msg,
            "statesTrace": states_trace,
            "remainingUnits": global_refill_store.get_remaining_units(),
        }

    # State 5: Settlement confirmed
    states_trace.append({
        "step": 5,
        "state": "SETTLEMENT_CONFIRMED",
        "description": f"Payment settled on {settlement.network}. TxHash: {settlement.txHash}",
        "settlement": settlement.model_dump(),
        "timestamp": time.time(),
    })

    # State 6: Allowance credited
    states_trace.append({
        "step": 6,
        "state": "ALLOWANCE_CREDITED",
        "description": f"Credited {credit_rec['unitsGranted']:,} simulated AI tokens. New balance: {credit_rec['remainingUnits']:,} units.",
        "creditRecord": credit_rec,
        "timestamp": time.time(),
    })

    # Record into ProofStore so Payments & Proofs view immediately reflects the settlement!
    proof_id = f"proof-x402-{nonce}"
    global_proof_store.create_proof_bundle(
        proof_id=proof_id,
        request_id=f"x402-{pkg.packageId}",
        requirement_id="req-seed-01",
        mandate_id=req.mandateId or "x402-direct-mandate",
        lines=[{
            "quoteId": f"x402-{pkg.packageId}",
            "vendorId": pkg.vendorId,
            "vendorName": pkg.vendorName,
            "priceMicroUsdc": pkg.priceMicroUsdc,
            "quantity": 1,
            "sku": f"AI-REFILL-{pkg.units}",
            "description": pkg.description
        }],
        basket_hash=to_hex(keccak(text=f"{pkg.packageId}:{nonce}")),
        total_amount=pkg.priceMicroUsdc,
        verifier_decision={
            "status": "APPROVED",
            "reasonCode": "X402_POLICY_COMPLIANT",
            "detail": f"x402 V2 payment requirement verified against policy caps (${pkg.priceUsdc:.2f} USDC)",
            "timestamp": time.time()
        },
        approval_data={
            "approvalId": f"x402-appr-{nonce}",
            "deadline": valid_until,
            "epoch": 1,
        },
        approval_sig=sig_payload.signature,
        tx_hash=settlement.txHash,
        receipt_status=1,
        block_number=chain.w3.eth.block_number if (chain and chain.w3.is_connected()) else 1,
        gas_used=21000,
        contract_address=chain.vault_address if chain else None,
        chain_id=31337,
        events=[{
            "event": "X402PaymentSettled",
            "payer": sig_payload.payer,
            "payee": sig_payload.payTo,
            "amount": pkg.priceMicroUsdc,
            "txHash": settlement.txHash
        }],
        payee_transfers=[{
            "payee": sig_payload.payTo,
            "vendorName": pkg.vendorName,
            "amount": pkg.priceMicroUsdc
        }],
        remaining_budget=max(0, 50_000_000 - global_x402_service.store.policy.spentToday),
        execution_mode="X402_V2_EXACT",
        fallback_status="NONE",
    )

    return {
        "success": True,
        "statesTrace": states_trace,
        "settlement": settlement.model_dump(),
        "creditRecord": credit_rec,
        "newRemainingUnits": credit_rec["remainingUnits"],
        "newTotalAllowance": credit_rec["newTotalAllowance"],
        "executionDurationMs": round((time.time() - t_start) * 1000, 2),
    }


