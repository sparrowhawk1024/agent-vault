/**
 * AgentVault Frontend API Client.
 * Connects to the local FastAPI backend.
 */

const API_BASE = "http://127.0.0.1:8000";

export interface SystemHealth {
  status: string;
  timestamp: number;
  chain: {
    connected: boolean;
    chainId: number;
    blockNumber: number;
    rpcUrl: string;
    vaultAddress: string;
    usdcAddress: string;
  };
  verifier: {
    status: string;
    address: string;
    wasteGuardActive: boolean;
  };
  qpiai: {
    optVersion: string;
    quantumVersion: string;
    optExecutionMode: string;
    qcloudStatus: string;
    simulatorBackend: string;
  };
}

export interface RefillPackage {
  packageId: string;
  name: string;
  vendorId: string;
  vendorName: string;
  units: number;
  priceMicroUsdc: number;
  priceUsdc: number;
  unitPriceMicros: number;
  isRecommended: boolean;
  isAllowedVendor: boolean;
  description: string;
  serviceType?: string;
  serviceName?: string;
  unitLabel?: string;
  isCapFlexible?: boolean;
}

export interface VendorServiceInfo {
  serviceType: string;
  serviceName: string;
  unitLabel: string;
  unitPriceMicros: number;
  vendorName: string;
  description: string;
  isAllowedVendor: boolean;
}

export interface AutoRefillPolicyData {
  enabled: boolean;
  maxSpendPerRefill: number;
  maxDailySpend: number;
  approvedVendor: string;
  refillThresholdPct: number;
  spentToday: number;
  lastRefillTimestamp: number | null;
  revoked: boolean;
}

export interface ChatMessageEntry {
  id: string;
  timestamp: number;
  prompt: string;
  response: string;
  tokensConsumed: number;
  remainingUnits: number;
  isLowBalance: boolean;
}

export interface RefillStatusResponse {
  totalAllowance: number;
  consumedUnits: number;
  remainingUnits: number;
  percentageRemaining: number;
  thresholdPct: number;
  isLowBalance: boolean;
  chatMessageCount: number;
  recentMessages: ChatMessageEntry[];
  policy: AutoRefillPolicyData;
  settlementCount: number;
  recentSettlements: any[];
  x402Config: {
    version: number;
    scheme: string;
    network: string;
    asset: string;
  };
  disclaimer: string;
}

export interface X402StateTrace {
  step: number;
  state: string;
  description: string;
  timestamp: number;
  error?: string;
  paymentRequired?: any;
  payloadPreview?: any;
  settlement?: any;
  creditRecord?: any;
}

export interface X402ClientPayResponse {
  success: boolean;
  error?: string;
  statesTrace: X402StateTrace[];
  settlement?: any;
  creditRecord?: any;
  newRemainingUnits?: number;
  newTotalAllowance?: number;
  executionDurationMs?: number;
}

export interface MandateDetails {
  creator: string;
  agent: string;
  token: string;
  totalBudget: number;
  spentTotal: number;
  perPurchaseCap: number;
  dailyCap: number;
  spentToday: number;
  lastSpendDay: number;
  validFrom: number;
  expiry: number;
  revoked: boolean;
  nonce: number;
}

export interface MandateResponse {
  mandateId: string;
  details: MandateDetails;
  remainingTotalBudget: number;
  remainingDailyCap: number;
  isActive: boolean;
}

export interface Requirement {
  requirementId: string;
  categoryRequirements: Record<string, number>;
  description: string;
  timestamp: number;
}

export interface CatalogQuote {
  quoteId: string;
  vendorId: string;
  vendorName: string;
  categoryId: string;
  categoryKey: string;
  skuId: string;
  units: number;
  price: number;
  validUntil: number;
  isAllowedVendor: boolean;
  signature: string;
  description: string;
}

export interface CatalogResponse {
  seed: number;
  count: number;
  quotes: CatalogQuote[];
  vendors: Record<string, any>;
  categories: Record<string, any>;
}

export interface BenchmarkReport {
  summary: {
    referenceOptimumCost: number;
    savingsVsGreedyPct: number;
    savingsVsVendorRulePct: number;
    seed: number;
  };
  solvers: Record<string, {
    solverName: string;
    executionMode: string;
    feasible: boolean;
    totalCost: number;
    coverage: Record<string, number>;
    lineCount: number;
    basketLines: any[];
    timingMs: number;
    errorMessage?: string;
  }>;
}

export interface ProofBundle {
  proofId: string;
  timestamp: number;
  requestId: string;
  requirementId: string;
  mandateId: string;
  basketHash: string;
  totalAmount: number;
  lines: any[];
  quoteIds: string[];
  verifierDecision: any;
  approval?: {
    approvalId: string;
    deadline: number;
    epoch: number;
    signature: string;
  };
  onChainExecution: {
    submitted: boolean;
    txHash?: string;
    receiptStatus?: number;
    blockNumber?: number;
    gasUsed?: number;
    contractAddress?: string;
    chainId?: number;
    payeeTransfers?: any[];
    remainingBudget?: number;
  };
  telemetry: {
    executionMode: string;
    fallbackStatus: string;
  };
}

export interface AttackCase {
  caseId: string;
  name: string;
  rejectionLayer: string;
  expectedCode: string;
  actualCode: string;
  passed: boolean;
  unauthorizedTransfer: boolean;
  details: string;
}

export interface AttackSuiteReport {
  suite: string;
  timestamp: number;
  totalCases: number;
  passedCases: number;
  unauthorizedTransfers: number;
  cases: AttackCase[];
}

export interface DashboardOverview {
  status: string;
  timestamp: number;
  chain: {
    connected: boolean;
    chainId: number;
    blockNumber: number | null;
    rpcUrl: string;
    vaultAddress: string | null;
    usdcAddress: string | null;
  };
  mandate: {
    mandateId: string | null;
    exists: boolean;
    isActive: boolean;
    totalBudget: number;
    spentTotal: number;
    remainingBudget: number;
    perPurchaseCap: number;
    dailyCap: number;
    revoked: boolean;
  };
  currentRequirement: Requirement | null;
  latestTxHash: string | null;
  latestAuditEvent: {
    index: number;
    eventType: string;
    timestamp: number;
    hash: string;
  } | null;
  paymentCounts: {
    confirmed: number;
    rejected: number;
    totalProofs: number;
  };
  verifier: {
    status: string;
    address: string;
    wasteGuardActive: boolean;
  };
  optimizer: {
    executionMode: string;
    benchmarkSavingsPct: number;
    referenceOptimumMicro: number;
  };
  qpiai: {
    optVersion: string;
    quantumVersion: string;
    optExecutionMode: string;
    qcloudStatus: string;
    remoteExecutionBlocked: boolean;
    remoteBlockReason: string;
    simulatorBackend: string;
  };
}

export const api = {
  getOverview: async (): Promise<DashboardOverview> => {
    const res = await fetch(`${API_BASE}/overview`);
    return res.json();
  },

  listMandates: async (): Promise<{ mandates: any[] }> => {
    const res = await fetch(`${API_BASE}/mandates`);
    return res.json();
  },

  resetDemo: async () => {
    const res = await fetch(`${API_BASE}/demo/reset`, { method: "POST" });
    return res.json();
  },

  getHealth: async (): Promise<SystemHealth> => {
    const res = await fetch(`${API_BASE}/health`);
    return res.json();
  },

  getMandate: async (id: string): Promise<MandateResponse> => {
    const res = await fetch(`${API_BASE}/mandates/${id}`);
    if (!res.ok) throw new Error("Mandate not found");
    return res.json();
  },

  prepareMandate: async (data: any) => {
    const res = await fetch(`${API_BASE}/mandates/prepare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    return res.json();
  },

  signMandateDev: async (mandate: any) => {
    const res = await fetch(`${API_BASE}/dev/sign-mandate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mandate }),
    });
    return res.json();
  },

  bootstrapMandate: async (): Promise<{ status: string; mandateId: string; mandate: any }> => {
    const res = await fetch(`${API_BASE}/mandates/bootstrap`, { method: "POST" });
    return res.json();
  },

  createMandate: async (mandate: any, ownerSignature: string) => {
    const res = await fetch(`${API_BASE}/mandates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mandate, ownerSignature }),
    });
    return res.json();
  },

  revokeMandate: async (mandateId: string) => {
    const res = await fetch(`${API_BASE}/owner/revoke?mandate_id=${mandateId}`, {
      method: "POST",
    });
    return res.json();
  },

  pauseContract: async () => {
    const res = await fetch(`${API_BASE}/owner/pause`, { method: "POST" });
    return res.json();
  },

  unpauseContract: async () => {
    const res = await fetch(`${API_BASE}/owner/unpause`, { method: "POST" });
    return res.json();
  },

  bumpEpoch: async () => {
    const res = await fetch(`${API_BASE}/owner/bump-epoch`, { method: "POST" });
    return res.json();
  },

  getRequirements: async (): Promise<Requirement[]> => {
    const res = await fetch(`${API_BASE}/meter/requirements`);
    return res.json();
  },

  getCatalog: async (seed: number = 1): Promise<CatalogResponse> => {
    const res = await fetch(`${API_BASE}/catalog?seed=${seed}`);
    return res.json();
  },

  optimize: async (requirementId: string, seed: number = 1, mandateId?: string): Promise<BenchmarkReport> => {
    const res = await fetch(`${API_BASE}/optimize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ requirementId, seed, mandateId }),
    });
    return res.json();
  },

  runAgent: async (params: {
    requirementId: string;
    mandateId: string;
    mode: "honest" | "gullible";
    attackType?: string;
    solver?: string;
    seed?: number;
  }) => {
    const res = await fetch(`${API_BASE}/agent/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    return res.json();
  },

  killVerifier: async () => {
    const res = await fetch(`${API_BASE}/admin/kill`, { method: "POST" });
    return res.json();
  },

  reviveVerifier: async () => {
    const res = await fetch(`${API_BASE}/admin/revive`, { method: "POST" });
    return res.json();
  },

  getProofs: async (): Promise<ProofBundle[]> => {
    const res = await fetch(`${API_BASE}/proofs`);
    return res.json();
  },

  getAuditEntries: async () => {
    const res = await fetch(`${API_BASE}/audit`);
    return res.json();
  },

  verifyAuditChain: async () => {
    const res = await fetch(`${API_BASE}/audit/verify`);
    return res.json();
  },

  getAttacks: async (): Promise<AttackSuiteReport> => {
    const res = await fetch(`${API_BASE}/attacks`);
    return res.json();
  },

  runAttacks: async () => {
    const res = await fetch(`${API_BASE}/attacks/run`, { method: "POST" });
    return res.json();
  },

  runQuantumExperiment: async (seed: number = 1) => {
    const res = await fetch(`${API_BASE}/quantum/run?seed=${seed}`, { method: "POST" });
    return res.json();
  },

  // --- x402 Auto-Refill & Simulated AI Chat ---
  getRefillStatus: async (): Promise<RefillStatusResponse> => {
    const res = await fetch(`${API_BASE}/refill/status`);
    return res.json();
  },

  sendChatMessage: async (prompt: string) => {
    const res = await fetch(`${API_BASE}/refill/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Chat request failed: ${res.status}`);
    }
    return res.json();
  },

  consumeRefillUnits: async (units: number, reason: string = "Presenter demo consumption") => {
    const res = await fetch(`${API_BASE}/refill/consume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ units, reason }),
    });
    return res.json();
  },

  getRefillPackages: async (): Promise<{
    count: number;
    packages: RefillPackage[];
    recommendedPackageId: string;
    vendorServices?: Record<string, VendorServiceInfo>;
    activePerRefillCap?: number;
    network: string;
    asset: string;
  }> => {
    const res = await fetch(`${API_BASE}/refill/packages`);
    return res.json();
  },

  calculateFlexiblePackage: async (
    vendor: string,
    spendMicroUsdc: number
  ): Promise<{ status: string; package: RefillPackage; policyCap: number; isWithinCap: boolean }> => {
    const res = await fetch(`${API_BASE}/refill/packages/calculate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vendor, spendMicroUsdc }),
    });
    return res.json();
  },

  updateRefillPolicy: async (policy: Partial<AutoRefillPolicyData>) => {
    const res = await fetch(`${API_BASE}/refill/policy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(policy),
    });
    return res.json();
  },

  resetRefillAllowance: async (initialAllowance: number = 5000) => {
    const res = await fetch(`${API_BASE}/refill/reset?initialAllowance=${initialAllowance}`, {
      method: "POST",
    });
    return res.json();
  },

  executeX402Pay: async (packageId: string, mandateId?: string, forceFail: boolean = false): Promise<X402ClientPayResponse> => {
    const res = await fetch(`${API_BASE}/x402/client/pay`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ packageId, mandateId, forceFail }),
    });
    return res.json();
  },
};
