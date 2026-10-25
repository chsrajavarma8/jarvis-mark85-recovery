from __future__ import annotations

import math

from .data_models import MissionDataset, Requirements, SAResult, TaskRequirement, UCSResult


def derive_requirements(ds: MissionDataset, ucs: UCSResult, sa: SAResult) -> Requirements:
    r = ds.rules
    x = sa.allocation
    failed_units = sorted(n.id for n in ds.network.nodes.values() if n.failed)
    battery = r["armor_battery_capacity_kWh"]
    deficit_kWh = battery * (r["target_state_of_charge"] - r["armor_state_of_charge"])
    slot_h = ds.mission["slot_minutes"] / 60.0
    charge_per_slot = r["charger_rating_kW"] * ucs.route_efficiency * slot_h

    rules = {
        "struct_restoration": (
            math.ceil(x["SR"] / r["struct_restoration_NU_per_slot"]),
            f"ceil(x_SR={x['SR']} / {r['struct_restoration_NU_per_slot']} NU per slot)"),
        "replenishment": (
            math.ceil(sa.material_used_NU / r["replenishment_NU_per_slot"]),
            f"ceil(M={sa.material_used_NU} NU consumed / {r['replenishment_NU_per_slot']} NU per slot)"),
        "sensor_calibration": (
            1 + math.ceil(x["SN"] / r["sensor_calibration_NU_per_slot"]),
            f"1 + ceil(x_SN={x['SN']} / {r['sensor_calibration_NU_per_slot']})"),
        "flight_sync": (
            1 + math.ceil(x["FS"] / r["flight_sync_NU_per_slot"]),
            f"1 + ceil(x_FS={x['FS']} / {r['flight_sync_NU_per_slot']})"),
        "thermal_inspection": (
            1 + math.ceil(sa.total_thermal_C / r["thermal_inspection_C_per_slot"]),
            f"1 + ceil(theta_total={sa.total_thermal_C:.2f} C / {r['thermal_inspection_C_per_slot']})"),
        "charging": (
            math.ceil(deficit_kWh / charge_per_slot),
            f"ceil(deficit {deficit_kWh:.0f} kWh / ({r['charger_rating_kW']} kW x eta={ucs.route_efficiency:.3f} x {slot_h} h))"),
        "converter_repair": (
            r["converter_repair_slots_per_failed_unit"] * len(failed_units),
            f"{r['converter_repair_slots_per_failed_unit']} slots x {len(failed_units)} failed unit(s) {failed_units}"),
    }

    tasks = []
    for t in ds.lab.tasks:
        if t.duration_rule.startswith("fixed:"):
            d, why = int(t.duration_rule.split(":")[1]), "fixed procedure length"
        else:
            d, why = rules[t.duration_rule]
        tasks.append(TaskRequirement(id=t.id, name=t.name, duration=max(1, int(d)),
                                     power_kW=float(t.power_kW), technicians=t.technicians,
                                     needs=dict(t.needs), after=list(t.after),
                                     deadline=t.deadline, derivation=why))
    notes = [
        f"Power cap for concurrent lab operations P_res = B - P_nano = "
        f"{ucs.power_budget_kW:.1f} - {sa.nano_power_kW:.1f} = {sa.residual_power_kW:.1f} kW",
        f"Route efficiency eta = {ucs.route_efficiency:.3f} scales the armor charging rate",
        f"Combined thermal load {sa.total_thermal_C:.2f} C sets the thermal-inspection length",
    ]
    return Requirements(tasks=tasks, power_cap_kW=sa.residual_power_kW,
                        horizon=ds.mission["horizon_slots"], technicians=ds.lab.technicians,
                        notes=notes)
