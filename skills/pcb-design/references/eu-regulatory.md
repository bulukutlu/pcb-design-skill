# EU regulatory overview (status researched 22 Nov 2026 — re-verify on EUR-Lex)

This is engineering guidance, not legal advice. Dates and harmonised-standard lists
change; check EUR-Lex and the Official Journal at run time before stating status.

## 1. First question: is the product "placed on the market"?
- In-house instruments built and used by the same organisation are generally not placed
  on the market.
- EMC Directive and RED exclude custom-built evaluation kits for professionals used
  solely at R&D facilities.
- Safety still matters: design lab equipment to EN 61010-1; inside CERN apply CERN HSE
  electrical-safety rules (CERN applies its own safety framework as an intergovernmental
  organisation — check with the local HSE unit).
- Sold or transferred to third parties (spin-off, external collaborators, customers) →
  full CE process.

## 2. Instruments
| Act | Scope / status |
|---|---|
| LVD 2014/35/EU | Electrical safety 50–1000 V AC / 75–1500 V DC. EN 62368-1 (ICT/AV), EN 61010-1 (lab/measurement). Below those voltages, GPSR covers safety. |
| EMC 2014/30/EU | Emissions/immunity: EN 55032, EN 55035, EN 61000-3-2/-3-3, EN 61000-4-x. |
| RED 2014/53/EU | Anything with a radio (incl. pre-certified BLE/Wi-Fi modules — the *product* still needs assessment). Cybersecurity Art. 3(3)(d/e/f) via Delegated Reg. (EU) 2022/30 applies since 1 Aug 2025; EN 18031-1/-2/-3 harmonised with restrictions (Implementing Decision (EU) 2025/138). Reported: Delegated Reg. (EU) 2026/339 repeals 2022/30 from 11 Dec 2027 when CRA takes over — single secondary source, verify. |
| CRA (EU) 2024/2847 | Products with digital elements. In force 10 Dec 2024. Notified-body provisions from 11 Jun 2026. Vulnerability/incident reporting (Art. 14) from 11 Sep 2026: early warning 24 h, notification 72 h, final report 14 days (vulnerability) / 1 month (incident), via ENISA single reporting platform — also for products already on the market. Full application incl. CE for digital elements: 11 Dec 2027. |
| RoHS 2011/65/EU + 2015/863 | 10 substances, 0.1 % w/w per homogeneous material (Cd 0.01 %). Lead-free assembly, RoHS BOM, supplier declarations. |
| WEEE 2012/19/EU | Crossed-out bin mark, producer registration per member state. |
| REACH 1907/2006 | SVHC > 0.1 % → Art. 33 information; SCIP database notification. |
| GPSR (EU) 2023/988 | Since 13 Dec 2024: general safety, traceability (manufacturer name/contact, type/batch on product). |
| Common charger (EU) 2022/2380 | USB-C receptacle + USB PD for listed portable devices; laptops since 28 Apr 2026. |
| Batteries (EU) 2023/1542 | Labelling, due diligence; user-removable/replaceable portable batteries from 18 Feb 2027 (check exemptions). |
| ESPR (EU) 2024/1781 | Ecodesign framework; product-specific acts and Digital Product Passport rolling out. |

## 3. CE process
1. Identify all applicable acts (table above).
2. Apply harmonised standards (presumption of conformity).
3. Conformity assessment: Module A (self-declaration) for most; notified body for RED
   when EN 18031 restrictions or partial application apply, and for some CRA classes.
4. Risk assessment (electrical, thermal, mechanical, fire, radiation, misuse).
5. Technical file: description, schematics, PCB, BOM, risk assessment, test reports,
   standards list, user manual/safety info, labels.
6. EU Declaration of Conformity: manufacturer, product ID, acts, standards, signatory,
   date.
7. Affix CE mark (≥ 5 mm), plus WEEE bin, traceability info.
8. Keep the file 10 years.

## 4. What the PCB designer must provide
- Creepage/clearance per end-product standard (hv-safety.md), fire enclosure/materials
  where needed (UL94 V-0 laminate is common), fusing and protection.
- EMC design + pre-compliance (emc-precompliance.md).
- RoHS-compliant BOM with declarations; lead-free finish (ENIG/HASL-LF).
- Labels/markings on silkscreen or product label: CE, WEEE bin, manufacturer, model,
  serial/batch, ratings, HV warnings.
- For digital products: secure-by-default firmware plan, update path, SBOM, vulnerability
  handling contact (CRA/RED).
