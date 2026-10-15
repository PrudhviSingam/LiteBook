import hashlib
import json
from decimal import Decimal
from typing import List, Dict, Any
from app.modules.gst.models import GSTSalesInvoice, GSTPurchaseInvoice
from app.modules.gst.validators import round_currency


def compute_gstr1_source_hash(invoices: List[GSTSalesInvoice]) -> str:
    """Computes a deterministic SHA-256 hash of all sales invoices affecting GSTR-1 for a period."""
    sorted_invs = sorted(
        invoices,
        key=lambda x: (str(x.invoice_number or "").upper(), str(x.invoice_date or "")),
    )
    data_elements = []
    for inv in sorted_invs:
        data_elements.append(
            f"{str(inv.invoice_number).strip().upper()}|{str(inv.invoice_date)}|{str(inv.customer_gstin or '').strip().upper()}|"
            f"{str(inv.place_of_supply or '').strip()}|{str(inv.invoice_type or '').strip()}|"
            f"{Decimal(str(inv.taxable_value or 0)):.2f}|{Decimal(str(inv.tax_rate or 0)):.2f}|"
            f"{Decimal(str(inv.cgst_amount or 0)):.2f}|{Decimal(str(inv.sgst_amount or 0)):.2f}|"
            f"{Decimal(str(inv.igst_amount or 0)):.2f}|{Decimal(str(inv.cess_amount or 0)):.2f}|"
            f"{Decimal(str(inv.total_amount or 0)):.2f}|{str(getattr(inv, 'is_active', True))}"
        )
    raw_str = "::".join(data_elements)
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def compute_gstr3b_source_hash(
    sales_invoices: List[GSTSalesInvoice],
    purchase_invoices: List[GSTPurchaseInvoice],
    itc_reversals: Dict[str, Any] = None,
) -> str:
    """Computes a deterministic SHA-256 hash of all sales, purchases, and reversals affecting GSTR-3B."""
    sorted_sales = sorted(
        sales_invoices,
        key=lambda x: (str(x.invoice_number or "").upper(), str(x.invoice_date or "")),
    )
    sorted_purchases = sorted(
        purchase_invoices,
        key=lambda x: (str(x.invoice_number or "").upper(), str(x.invoice_date or "")),
    )

    parts = ["SALES:" + compute_gstr1_source_hash(sorted_sales)]

    purch_elements = []
    for p in sorted_purchases:
        purch_elements.append(
            f"{str(p.invoice_number).strip().upper()}|{str(p.invoice_date)}|{str(p.supplier_gstin or '').strip().upper()}|"
            f"{str(p.place_of_supply or '').strip()}|{str(p.itc_eligibility or 'ELIGIBLE').strip().upper()}|"
            f"{Decimal(str(p.taxable_value or 0)):.2f}|{Decimal(str(p.cgst_amount or 0)):.2f}|"
            f"{Decimal(str(p.sgst_amount or 0)):.2f}|{Decimal(str(p.igst_amount or 0)):.2f}|"
            f"{Decimal(str(p.cess_amount or 0)):.2f}|{Decimal(str(p.total_amount or 0)):.2f}"
        )
    parts.append(
        "PURCHASES:"
        + hashlib.sha256("::".join(purch_elements).encode("utf-8")).hexdigest()
    )

    rev_str = json.dumps(itc_reversals or {}, sort_keys=True)
    parts.append("REVERSALS:" + rev_str)

    return hashlib.sha256("###".join(parts).encode("utf-8")).hexdigest()


def aggregate_gstr1(invoices: List[GSTSalesInvoice]) -> Dict[str, Any]:
    """Aggregates sales invoices into statutory GSTR-1 return tables.

    Tables covered:
    - Table 4: B2B Invoices (Registered Taxpayers)
    - Table 5: B2CL (Inter-state Unregistered > ₹2,50,000)
    - Table 7: B2CS (All Intra-state Unregistered or Inter-state <= ₹2,50,000)
    - Table 6A: Exports (With or Without Tax)
    - Table 9B: Credit / Debit Notes (Registered CDNR & Unregistered CDNUR)
    - Table 8: Nil-rated, Exempted, and Non-GST Supplies
    """
    total_taxable = Decimal("0.00")
    total_igst = Decimal("0.00")
    total_cgst = Decimal("0.00")
    total_sgst = Decimal("0.00")
    total_cess = Decimal("0.00")
    total_val = Decimal("0.00")

    tables: Dict[str, Dict[str, Any]] = {
        "b2b": {
            "count": 0,
            "taxable_value": Decimal("0.00"),
            "igst": Decimal("0.00"),
            "cgst": Decimal("0.00"),
            "sgst": Decimal("0.00"),
            "cess": Decimal("0.00"),
            "total": Decimal("0.00"),
            "records": [],
        },
        "b2cl": {
            "count": 0,
            "taxable_value": Decimal("0.00"),
            "igst": Decimal("0.00"),
            "total": Decimal("0.00"),
            "records": [],
        },
        "b2cs": {
            "count": 0,
            "taxable_value": Decimal("0.00"),
            "igst": Decimal("0.00"),
            "cgst": Decimal("0.00"),
            "sgst": Decimal("0.00"),
            "cess": Decimal("0.00"),
            "total": Decimal("0.00"),
        },
        "exports": {
            "count": 0,
            "taxable_value": Decimal("0.00"),
            "igst": Decimal("0.00"),
            "total": Decimal("0.00"),
            "records": [],
        },
        "cdnr": {
            "count": 0,
            "taxable_value": Decimal("0.00"),
            "igst": Decimal("0.00"),
            "cgst": Decimal("0.00"),
            "sgst": Decimal("0.00"),
            "cess": Decimal("0.00"),
            "total": Decimal("0.00"),
            "records": [],
        },
        "cdnur": {
            "count": 0,
            "taxable_value": Decimal("0.00"),
            "igst": Decimal("0.00"),
            "total": Decimal("0.00"),
            "records": [],
        },
        "nil_exempt": {
            "count": 0,
            "nil_rated": Decimal("0.00"),
            "exempted": Decimal("0.00"),
            "non_gst": Decimal("0.00"),
            "total": Decimal("0.00"),
        },
    }

    for inv in invoices:
        taxable = Decimal(str(inv.taxable_value))
        igst = Decimal(str(inv.igst_amount))
        cgst = Decimal(str(inv.cgst_amount))
        sgst = Decimal(str(inv.sgst_amount))
        cess = Decimal(str(inv.cess_amount))
        inv_total = Decimal(str(inv.total_amount))

        total_taxable += taxable
        total_igst += igst
        total_cgst += cgst
        total_sgst += sgst
        total_cess += cess
        total_val += inv_total

        inv_type = (inv.invoice_type or "B2B").upper()
        has_customer_gstin = bool(
            inv.customer_gstin and len(inv.customer_gstin.strip()) == 15
        )
        is_inter_state = inv.supply_type == "INTER_STATE"

        # Table routing
        if inv_type == "CDNR":
            t = tables["cdnr"]
            t["count"] += 1
            t["taxable_value"] += taxable
            t["igst"] += igst
            t["cgst"] += cgst
            t["sgst"] += sgst
            t["cess"] += cess
            t["total"] += inv_total
            t["records"].append(
                {
                    "invoice_number": inv.invoice_number,
                    "invoice_date": inv.invoice_date,
                    "customer_gstin": inv.customer_gstin,
                    "customer_name": inv.customer_name,
                    "taxable_value": str(taxable),
                    "total_amount": str(inv_total),
                }
            )
        elif inv_type == "CDNUR":
            t = tables["cdnur"]
            t["count"] += 1
            t["taxable_value"] += taxable
            t["igst"] += igst
            t["total"] += inv_total
            t["records"].append(
                {
                    "invoice_number": inv.invoice_number,
                    "invoice_date": inv.invoice_date,
                    "taxable_value": str(taxable),
                    "total_amount": str(inv_total),
                }
            )
        elif inv_type == "EXPORT":
            t = tables["exports"]
            t["count"] += 1
            t["taxable_value"] += taxable
            t["igst"] += igst
            t["total"] += inv_total
            t["records"].append(
                {
                    "invoice_number": inv.invoice_number,
                    "invoice_date": inv.invoice_date,
                    "taxable_value": str(taxable),
                    "total_amount": str(inv_total),
                }
            )
        elif inv_type == "NIL_EXEMPT" or inv.tax_rate == Decimal("0.00"):
            t = tables["nil_exempt"]
            t["count"] += 1
            t["exempted"] += taxable
            t["total"] += taxable
        elif has_customer_gstin:
            # B2B Table 4
            t = tables["b2b"]
            t["count"] += 1
            t["taxable_value"] += taxable
            t["igst"] += igst
            t["cgst"] += cgst
            t["sgst"] += sgst
            t["cess"] += cess
            t["total"] += inv_total
            t["records"].append(
                {
                    "invoice_number": inv.invoice_number,
                    "invoice_date": inv.invoice_date,
                    "customer_gstin": inv.customer_gstin,
                    "customer_name": inv.customer_name,
                    "place_of_supply": inv.place_of_supply,
                    "taxable_value": str(taxable),
                    "tax_rate": str(inv.tax_rate),
                    "total_amount": str(inv_total),
                }
            )
        else:
            # Unregistered Recipient: B2CL vs B2CS
            # B2C Large: Inter-state invoice value strictly greater than 2.5 Lakhs (₹250,000)
            if is_inter_state and inv_total > Decimal("250000.00"):
                t = tables["b2cl"]
                t["count"] += 1
                t["taxable_value"] += taxable
                t["igst"] += igst
                t["total"] += inv_total
                t["records"].append(
                    {
                        "invoice_number": inv.invoice_number,
                        "invoice_date": inv.invoice_date,
                        "customer_name": inv.customer_name,
                        "place_of_supply": inv.place_of_supply,
                        "taxable_value": str(taxable),
                        "total_amount": str(inv_total),
                    }
                )
            else:
                t = tables["b2cs"]
                t["count"] += 1
                t["taxable_value"] += taxable
                t["igst"] += igst
                t["cgst"] += cgst
                t["sgst"] += sgst
                t["cess"] += cess
                t["total"] += inv_total

    # Serialize table summaries to JSON strings
    def serialize_table(tbl: dict) -> str:
        res = {}
        for k, v in tbl.items():
            if isinstance(v, Decimal):
                res[k] = str(round_currency(v))
            else:
                res[k] = v
        return json.dumps(res)

    return {
        "total_taxable_value": round_currency(total_taxable),
        "total_igst": round_currency(total_igst),
        "total_cgst": round_currency(total_cgst),
        "total_sgst": round_currency(total_sgst),
        "total_cess": round_currency(total_cess),
        "total_invoice_value": round_currency(total_val),
        "total_invoices_count": len(invoices),
        "tables": {
            k: {k2: str(v2) if isinstance(v2, Decimal) else v2 for k2, v2 in v.items()}
            for k, v in tables.items()
        },
        "b2b_summary": serialize_table(tables["b2b"]),
        "b2cl_summary": serialize_table(tables["b2cl"]),
        "b2cs_summary": serialize_table(tables["b2cs"]),
        "export_summary": serialize_table(tables["exports"]),
        "cdnr_summary": serialize_table(tables["cdnr"]),
        "nil_exempt_summary": serialize_table(tables["nil_exempt"]),
    }


def calculate_gstr3b(
    sales_invoices: List[GSTSalesInvoice],
    purchase_invoices: List[GSTPurchaseInvoice],
    itc_reversals: Dict[str, Decimal] = None,
) -> Dict[str, Any]:
    """Calculates statutory GSTR-3B tax computation, ITC availability, reversals, and net liability.

    Adheres strictly to the GST Council set-off rules:
    - IGST credit utilized against IGST, then CGST/SGST.
    - CGST credit utilized against CGST, then IGST.
    - SGST credit utilized against SGST, then IGST.
    - CGST and SGST cannot cross-utilize.
    """
    if itc_reversals is None:
        itc_reversals = {}

    rev_igst = round_currency(Decimal(str(itc_reversals.get("igst", "0.00"))))
    rev_cgst = round_currency(Decimal(str(itc_reversals.get("cgst", "0.00"))))
    rev_sgst = round_currency(Decimal(str(itc_reversals.get("sgst", "0.00"))))
    rev_cess = round_currency(Decimal(str(itc_reversals.get("cess", "0.00"))))

    # 1. 3.1 Outward supplies calculation
    outward_taxable = Decimal("0.00")
    outward_igst = Decimal("0.00")
    outward_cgst = Decimal("0.00")
    outward_sgst = Decimal("0.00")
    outward_cess = Decimal("0.00")

    interstate_unreg_taxable = Decimal("0.00")
    interstate_unreg_igst = Decimal("0.00")

    for s in sales_invoices:
        taxable = Decimal(str(s.taxable_value))
        igst = Decimal(str(s.igst_amount))
        cgst = Decimal(str(s.cgst_amount))
        sgst = Decimal(str(s.sgst_amount))
        cess = Decimal(str(s.cess_amount))

        outward_taxable += taxable
        outward_igst += igst
        outward_cgst += cgst
        outward_sgst += sgst
        outward_cess += cess

        # Unregistered inter-state supplies (Table 3.2)
        has_gstin = bool(s.customer_gstin and len(s.customer_gstin.strip()) == 15)
        if s.supply_type == "INTER_STATE" and not has_gstin:
            interstate_unreg_taxable += taxable
            interstate_unreg_igst += igst

    # 2. 4 Eligible ITC from Purchase Register
    itc_all_other_igst = Decimal("0.00")
    itc_all_other_cgst = Decimal("0.00")
    itc_all_other_sgst = Decimal("0.00")
    itc_all_other_cess = Decimal("0.00")

    inward_exempt = Decimal("0.00")

    for p in purchase_invoices:
        if (p.itc_eligibility or "ELIGIBLE").upper() == "ELIGIBLE":
            itc_all_other_igst += Decimal(str(p.igst_amount))
            itc_all_other_cgst += Decimal(str(p.cgst_amount))
            itc_all_other_sgst += Decimal(str(p.sgst_amount))
            itc_all_other_cess += Decimal(str(p.cess_amount))
        elif (p.invoice_type or "").upper() == "NIL_EXEMPT":
            inward_exempt += Decimal(str(p.taxable_value))

    # Net ITC Available = Gross Eligible ITC - Reversals
    net_itc_igst = max(Decimal("0.00"), itc_all_other_igst - rev_igst)
    net_itc_cgst = max(Decimal("0.00"), itc_all_other_cgst - rev_cgst)
    net_itc_sgst = max(Decimal("0.00"), itc_all_other_sgst - rev_sgst)
    net_itc_cess = max(Decimal("0.00"), itc_all_other_cess - rev_cess)

    # 3. 6.1 Tax Liability Set-off Execution
    # Gross Liabilities
    rem_liab_igst = outward_igst
    rem_liab_cgst = outward_cgst
    rem_liab_sgst = outward_sgst
    rem_liab_cess = outward_cess

    # Available Balances
    avail_igst = net_itc_igst
    avail_cgst = net_itc_cgst
    avail_sgst = net_itc_sgst
    avail_cess = net_itc_cess

    # Step A: IGST Credit against IGST Liability
    use_igst_for_igst = min(avail_igst, rem_liab_igst)
    rem_liab_igst -= use_igst_for_igst
    avail_igst -= use_igst_for_igst

    # Step B: Remaining IGST Credit against CGST, then SGST Liability
    use_igst_for_cgst = min(avail_igst, rem_liab_cgst)
    rem_liab_cgst -= use_igst_for_cgst
    avail_igst -= use_igst_for_cgst

    use_igst_for_sgst = min(avail_igst, rem_liab_sgst)
    rem_liab_sgst -= use_igst_for_sgst
    avail_igst -= use_igst_for_sgst

    # Step C: CGST Credit against CGST Liability, then IGST
    use_cgst_for_cgst = min(avail_cgst, rem_liab_cgst)
    rem_liab_cgst -= use_cgst_for_cgst
    avail_cgst -= use_cgst_for_cgst

    use_cgst_for_igst = min(avail_cgst, rem_liab_igst)
    rem_liab_igst -= use_cgst_for_igst
    avail_cgst -= use_cgst_for_igst

    # Step D: SGST Credit against SGST Liability, then IGST
    use_sgst_for_sgst = min(avail_sgst, rem_liab_sgst)
    rem_liab_sgst -= use_sgst_for_sgst
    avail_sgst -= use_sgst_for_sgst

    use_sgst_for_igst = min(avail_sgst, rem_liab_igst)
    rem_liab_igst -= use_sgst_for_igst
    avail_sgst -= use_sgst_for_igst

    # Step E: Cess Credit against Cess Liability only
    use_cess_for_cess = min(avail_cess, rem_liab_cess)
    rem_liab_cess -= use_cess_for_cess
    avail_cess -= use_cess_for_cess

    total_net_payable = rem_liab_igst + rem_liab_cgst + rem_liab_sgst + rem_liab_cess

    return {
        # Table 3.1
        "outward_taxable_value": round_currency(outward_taxable),
        "outward_igst": round_currency(outward_igst),
        "outward_cgst": round_currency(outward_cgst),
        "outward_sgst": round_currency(outward_sgst),
        "outward_cess": round_currency(outward_cess),
        # Table 3.2
        "interstate_unregistered_taxable": round_currency(interstate_unreg_taxable),
        "interstate_unregistered_igst": round_currency(interstate_unreg_igst),
        # Table 4 ITC Gross
        "itc_all_other_igst": round_currency(itc_all_other_igst),
        "itc_all_other_cgst": round_currency(itc_all_other_cgst),
        "itc_all_other_sgst": round_currency(itc_all_other_sgst),
        "itc_all_other_cess": round_currency(itc_all_other_cess),
        # Table 4 ITC Reversals
        "itc_reversed_igst": round_currency(rev_igst),
        "itc_reversed_cgst": round_currency(rev_cgst),
        "itc_reversed_sgst": round_currency(rev_sgst),
        "itc_reversed_cess": round_currency(rev_cess),
        # Table 4 Net ITC
        "net_itc_igst": round_currency(net_itc_igst),
        "net_itc_cgst": round_currency(net_itc_cgst),
        "net_itc_sgst": round_currency(net_itc_sgst),
        "net_itc_cess": round_currency(net_itc_cess),
        # Table 5
        "inward_exempt_nil": round_currency(inward_exempt),
        # Table 6.1 Net Tax Payable
        "net_tax_payable_igst": round_currency(rem_liab_igst),
        "net_tax_payable_cgst": round_currency(rem_liab_cgst),
        "net_tax_payable_sgst": round_currency(rem_liab_sgst),
        "net_tax_payable_cess": round_currency(rem_liab_cess),
        "total_net_tax_payable": round_currency(total_net_payable),
        # Utilization breakdown for transparency
        "utilization": {
            "use_igst_for_igst": str(round_currency(use_igst_for_igst)),
            "use_igst_for_cgst": str(round_currency(use_igst_for_cgst)),
            "use_igst_for_sgst": str(round_currency(use_igst_for_sgst)),
            "use_cgst_for_cgst": str(round_currency(use_cgst_for_cgst)),
            "use_cgst_for_igst": str(round_currency(use_cgst_for_igst)),
            "use_sgst_for_sgst": str(round_currency(use_sgst_for_sgst)),
            "use_sgst_for_igst": str(round_currency(use_sgst_for_igst)),
            "use_cess_for_cess": str(round_currency(use_cess_for_cess)),
        },
    }
