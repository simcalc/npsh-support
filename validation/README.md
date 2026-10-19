# Physical validation evidence protocol

Status: **MEASUREMENTS_REQUIRED**. The inspected material provides software,
synthetic contract cases, native educational runs and discretization evidence.
None is an independent exact-pump measurement set. The CSV template is empty
intentionally; values displayed by Main are calculated references, not rig data.

## Dataset and comparison

1. Preserve raw measured files unchanged, with source, revision, units, SHA-256,
   instrument/calibration information, repeatability, uncertainty definition
   and measurement procedure. Keep calibration data separate from validation.
2. Match exact product, variant, stage, impeller, RPM, flow, fluid/temperature,
   pressure reference, report planes, datum and head/NPSH criterion. A different
   pump's curve cannot establish exact-pump CFD validation. Published compatible
   manufacturer data remain usable for source comparisons without a certificate.
3. For measured static pressures at specified planes, use the declared energy
   basis: H = (p_d-p_s)/(rho*g) + (v_d^2-v_s^2)/(2*g) + z_d-z_s, with kinetic
   energy correction factors if required by the measurement definition. Do not
   add velocity head again when the source already reports total pressure.
4. NPSHA at the suction reference is (p_s,abs-p_v)/(rho*g) + v_s^2/(2*g)
   plus the explicitly declared plane-to-NPSH-datum elevation correction.
   Submerged or different datum cases require the matching convention.
   NPSH3 needs a fixed-Q/RPM noncavitating reference and an observed 3% head
   drop. For a multistage pump use first-stage head where required. Other
   manufacturer criteria retain their original labels.
5. Compare E_i = S_i-D_i on compatible quantities/conditions. Report signed
   bias, MAE and RMSE separately; relative error is undefined at D_i=0.
   Interpolation only uses known points inside the shared domain.
6. Quantify experimental, numerical and input uncertainty separately. If
   statistically independent standard uncertainties apply,
   u_val = sqrt(u_exp^2+u_num^2+u_input^2). Otherwise retain the actual covariance
   model. A coverage factor is explicit; spread is not automatically standard
   uncertainty, GCI or a confidence interval. Do not invent uncertainty values.
7. Declare tolerances and decision rules before inspecting agreement. No
   universal percentage, standard-compliance label, physical-validation pass
   or Pump-safe status is inferred from this protocol alone.

Missing uncertainty permits a labeled nominal comparison; it limits the
uncertainty claim. Missing measurements limits physical validation. Neither
should stop valid independent system, pump or Lab calculations.

Native simulation acceptance also needs geometry, boundary conditions,
conservation, convergence and independent mesh/time/model sensitivity. A
checksum proves byte integrity, not physical truth or solver execution.

References for the method and its limitations:

- [Hydraulic Institute pump/system fundamentals](https://datatool.pumps.org/pump-fundamentals/combined.html)
- [ASME V&V 20 overview](https://www.asme.org/codes-standards/find-codes-standards/standard-for-verification-and-validation-in-computational-fluid-dynamics-and-heat-transfer/2009/print-book)
- [Numerical Prediction of the NPSH Characteristics in Centrifugal Pumps](https://doi.org/10.3390/fluids10100274)

The project previously assessed these research references. This protocol is
an evidence collection guide and does not claim full compliance with a standard.
Book PDF/pages are not included in this hub or sent to Supabase.
