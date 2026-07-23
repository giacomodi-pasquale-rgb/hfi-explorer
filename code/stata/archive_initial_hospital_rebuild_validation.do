clear all
set more off

* Rebuilt from CMS Provider Data Catalog:
* Hospital General Information and Patient survey (HCAHPS) - Hospital.
import delimited "derived/nyc_hcahps_validation_analysis_file.csv", clear varnames(1)

destring fragmentation_index fragmentation access_z communication_index patient_experience_index ///
    hcahps_nurse_comm_linear hcahps_doctor_comm_linear hcahps_medicine_comm_linear ///
    hcahps_discharge_linear hcahps_overall_linear hcahps_recommend_linear ///
    hospital_overall_rating, replace force

gen public_hospital = public_private_designation == "Public"
encode hospital_system, gen(hospital_system_id)

summarize fragmentation_index fragmentation access_z communication_index patient_experience_index ///
    hcahps_nurse_comm_linear hcahps_doctor_comm_linear hospital_overall_rating

* Main construct-validation models.
regress communication_index fragmentation_index, vce(hc3)
regress communication_index fragmentation_index hospital_overall_rating, vce(hc3)

* Patient-experience index sensitivity.
regress patient_experience_index fragmentation_index, vce(hc3)
regress patient_experience_index fragmentation_index hospital_overall_rating, vce(hc3)

* Public/private sensitivity. Interpret cautiously because n remains modest.
regress communication_index fragmentation_index public_hospital, vce(hc3)
regress communication_index fragmentation_index hospital_overall_rating public_hospital, vce(hc3)

* Optional system fixed-effect sensitivity. Interpret cautiously because many systems
* have only one or two hospitals in the validation sample.
regress communication_index fragmentation_index i.hospital_system_id, vce(hc3)
