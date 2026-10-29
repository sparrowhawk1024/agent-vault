import json
import itertools

def main():
    # 1. Load the manifest
    with open("evidence/runs/phase3_reduced_instance_manifest.json", "r") as f:
        manifest = json.load(f)

    print("=" * 70)
    print("EXHAUSTIVE STATE ENUMERATION & MANIFEST RECOMPUTATION")
    print("=" * 70)

    # 2. Extract quotes and requirements from manifest
    var_map = manifest["variableMapping"]
    quotes_8 = [var_map[f"q{i}"] for i in range(8)]
    
    api_quotes = [q for q in quotes_8 if q["category"] == "API_CALLS"]
    ai_quotes = [q for q in quotes_8 if q["category"] == "AI_CREDITS"]
    storage_quotes = [q for q in quotes_8 if q["category"] == "STORAGE"]

    req_api = 1000
    req_ai = 500
    req_storage = 100

    print(f"\nCandidate Quotes from Manifest (8 variables):")
    print(f"  API Calls (req={req_api}):")
    for q in api_quotes:
        print(f"    - {q['name']}: units={q['units']}, price={q['price']} micro-USDC")
    print(f"  AI Credits (req={req_ai}):")
    for q in ai_quotes:
        print(f"    - {q['name']}: units={q['units']}, price={q['price']} micro-USDC")
    print(f"  Storage (req={req_storage}):")
    for q in storage_quotes:
        print(f"    - {q['name']}: units={q['units']}, price={q['price']} micro-USDC")

    # 3. Independent Enumeration over the 8 decision variables (2^8 = 256)
    feasible_8 = []
    infeasible_8 = []

    for bits in itertools.product([0, 1], repeat=8):
        x = list(bits)
        cov_api = sum(quotes_8[i]["units"] * x[i] for i in range(3))
        cov_ai = sum(quotes_8[i]["units"] * x[i] for i in range(3, 6))
        cov_storage = sum(quotes_8[i]["units"] * x[i] for i in range(6, 8))

        is_feas = (cov_api >= req_api) and (cov_ai >= req_ai) and (cov_storage >= req_storage)
        
        cost = sum(quotes_8[i]["price"] * x[i] for i in range(8))
        record = {
            "x": x,
            "cov_api": cov_api,
            "cov_ai": cov_ai,
            "cov_storage": cov_storage,
            "cost": cost,
            "feasible": is_feas
        }
        if is_feas:
            feasible_8.append(record)
        else:
            infeasible_8.append(record)

    total_8 = len(feasible_8) + len(infeasible_8)

    print("\n" + "-" * 70)
    print("INDEPENDENT RECOMPUTATION (8-Variable Procurement Decision Space):")
    print(f"  Total Decision States (2^8):   {total_8}")
    print(f"  Feasible Decision States:      {len(feasible_8)}")
    print(f"  Infeasible Decision States:    {len(infeasible_8)}")
    print("-" * 70)

    # Breakdown per category
    api_feas_count = sum(1 for bits in itertools.product([0, 1], repeat=3) if sum(api_quotes[i]["units"] * bits[i] for i in range(3)) >= req_api)
    ai_feas_count = sum(1 for bits in itertools.product([0, 1], repeat=3) if sum(ai_quotes[i]["units"] * bits[i] for i in range(3)) >= req_ai)
    storage_feas_count = sum(1 for bits in itertools.product([0, 1], repeat=2) if sum(storage_quotes[i]["units"] * bits[i] for i in range(2)) >= req_storage)

    print(f"\nCategory-by-Category Combinatorial Product:")
    print(f"  API feasible assignments:     {api_feas_count} / 8  (only (0,0,0) fails)")
    print(f"  AI feasible assignments:      {ai_feas_count} / 8  (only (0,0,0) fails)")
    print(f"  Storage feasible assignments: {storage_feas_count} / 4  (only (0,0) fails)")
    print(f"  Independent Product:          {api_feas_count} * {ai_feas_count} * {storage_feas_count} = {api_feas_count * ai_feas_count * storage_feas_count}")

    # 4. Independent Enumeration over the 13-Qubit Space (2^13 = 8,192 states)
    # 8 offer binaries + 5 slack binaries (2 API, 2 AI, 1 Storage)
    total_13 = 8192
    hamiltonian_exact_feasible = []  # Feasible AND exact slack (H_penalty == 0)
    hamiltonian_offer_feasible = []  # Offer basket satisfies coverage (any slack)
    hamiltonian_infeasible = []      # Offer basket fails coverage

    for bits in itertools.product([0, 1], repeat=13):
        x = list(bits[:8])
        s = list(bits[8:])
        s_api = s[0] + 2 * s[1]
        s_ai = s[2] + 2 * s[3]
        s_storage = s[4]

        cov_api = sum(quotes_8[i]["units"] * x[i] for i in range(3))
        cov_ai = sum(quotes_8[i]["units"] * x[i] for i in range(3, 6))
        cov_storage = sum(quotes_8[i]["units"] * x[i] for i in range(6, 8))

        is_offer_feas = (cov_api >= req_api) and (cov_ai >= req_ai) and (cov_storage >= req_storage)

        surplus_api = (cov_api - req_api) // 1000
        surplus_ai = (cov_ai - req_ai) // 500
        surplus_storage = (cov_storage - req_storage) // 100

        # Exact penalty equality:
        # x0 + x1 + 2*x2 - 1 - (s_api) == 0
        # x3 + x4 + 2*x5 - 1 - (s_ai) == 0
        # x6 + x7 - 1 - s_storage == 0
        eq_api = (cov_api // 1000 - 1 - s_api == 0)
        eq_ai = (cov_ai // 500 - 1 - s_ai == 0)
        eq_storage = (cov_storage // 100 - 1 - s_storage == 0)
        exact_penalty_zero = eq_api and eq_ai and eq_storage

        if exact_penalty_zero:
            hamiltonian_exact_feasible.append(bits)

        if is_offer_feas:
            hamiltonian_offer_feasible.append(bits)
        else:
            hamiltonian_infeasible.append(bits)

    print("\n" + "=" * 70)
    print("13-QUBIT FULL HILBERT SPACE COUNTS (2^13 = 8,192 states):")
    print(f"  Total Basis States:                                     {total_13:,}")
    print(f"  Exact Feasible Ground-Manifold States (H_penalty == 0): {len(hamiltonian_exact_feasible):,}")
    print(f"  Offer-Feasible States (offer coverage >= requirements): {len(hamiltonian_offer_feasible):,}  ({len(feasible_8)} * 32)")
    print(f"  Infeasible States (deficit in >= 1 category):           {len(hamiltonian_infeasible):,}  ({len(infeasible_8)} * 32)")
    print("=" * 70)

    print("\nEXPLANATION OF THE 147 COUNT:")
    print("  1. In the 8-variable procurement decision space x in {0,1}^8:")
    print("     The catalog provides 3 API quotes, 3 AI quotes, and 2 Storage quotes.")
    print("     To satisfy coverage:")
    print("       - API: 7 out of 8 combinations meet the requirement >= 1000.")
    print("       - AI: 7 out of 8 combinations meet the requirement >= 500.")
    print("       - Storage: 3 out of 4 combinations meet the requirement >= 100.")
    print("     Therefore, exactly 7 * 7 * 3 = 147 offer configurations are feasible,")
    print("     and 256 - 147 = 109 offer configurations are infeasible.")
    print("")
    print("  2. In the 13-qubit encoding with 5 slack variables:")
    print("     There are 2^5 = 32 slack configurations per offer configuration.")
    print("     - If 'feasible' is evaluated solely on the 8 offer variables:")
    print("       Total feasible = 147 * 32 = 4,704 states.")
    print("       Total infeasible = 109 * 32 = 3,488 states.")
    print("       Total basis states = 4,704 + 3,488 = 8,192.")
    print("     - If 'feasible' is evaluated on the exact Hamiltonian zero-penalty condition:")
    print("       Each of the 147 feasible offer baskets has a UNIQUE surplus (surplus_api, surplus_ai, surplus_storage).")
    print("       Because the binary slack representation (2 bits for API surplus 0..3, 2 bits for AI surplus 0..3,")
    print("       1 bit for storage surplus 0..1) uniquely maps each integer surplus, there is EXACTLY ONE slack setting")
    print("       per feasible basket that yields H_penalty = 0.")
    print("       Therefore, the number of zero-penalty feasible basis states is EXACTLY 147.")
    print("=" * 70)

if __name__ == "__main__":
    main()

