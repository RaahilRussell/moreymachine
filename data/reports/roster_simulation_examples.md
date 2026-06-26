# Roster Simulation Examples

The simulation assigns roster slots before recommendation scoring.

## Center Candidates

| Player | Primary Slot | Role | Starter | Playoff | Flags |
| --- | --- | --- | --- | --- | --- |
| Al Horford | matchup_big | matchup big and regular-season size option | False | True |  |
| Alex Sarr | matchup_big | non-Embiid center minutes, backup center, or matchup big | False | True | normal_starting_center_slot_blocked_by_embiid |
| Alperen Sengun | theoretical_star_upgrade | theoretical star upgrade, not a realistic roster-slot projection | False | False | normal_starting_center_slot_blocked_by_embiid, theoretical_or_unavailable_candidate |
| Amari Williams | regular_season_depth | non-Embiid center minutes, backup center, or matchup big | False | False | normal_starting_center_slot_blocked_by_embiid |
| Anthony Davis | theoretical_star_upgrade | theoretical star upgrade, not a realistic roster-slot projection | False | False | normal_starting_center_slot_blocked_by_embiid, theoretical_or_unavailable_candidate |
| Ariel Hukporti | regular_season_depth | non-Embiid center minutes, backup center, or matchup big | False | False | normal_starting_center_slot_blocked_by_embiid |
| Bam Adebayo | theoretical_star_upgrade | theoretical star upgrade, not a realistic roster-slot projection | False | False | normal_starting_center_slot_blocked_by_embiid, theoretical_or_unavailable_candidate |
| Bismack Biyombo | regular_season_depth | non-Embiid center minutes, backup center, or matchup big | False | False | normal_starting_center_slot_blocked_by_embiid |
| Branden Carlson | regular_season_depth | non-Embiid center minutes, backup center, or matchup big | False | False | normal_starting_center_slot_blocked_by_embiid, candidate_status_manual_review_required |
| Brook Lopez | matchup_big | non-Embiid center minutes, backup center, or matchup big | False | True | normal_starting_center_slot_blocked_by_embiid |
| Charles Bassey | regular_season_depth | non-Embiid center minutes, backup center, or matchup big | False | False | normal_starting_center_slot_blocked_by_embiid |
| Chet Holmgren | theoretical_star_upgrade | theoretical star upgrade, not a realistic roster-slot projection | False | False | theoretical_or_unavailable_candidate |
| Christian Koloko | regular_season_depth | non-Embiid center minutes, backup center, or matchup big | False | False | normal_starting_center_slot_blocked_by_embiid |
| Clint Capela | matchup_big | non-Embiid center minutes, backup center, or matchup big | False | True | normal_starting_center_slot_blocked_by_embiid |
| Colin Castleton | regular_season_depth | non-Embiid center minutes, backup center, or matchup big | False | False | normal_starting_center_slot_blocked_by_embiid, candidate_status_manual_review_required |

## Clear Role Examples

| Player | Primary Slot | Role | Starter | Playoff | Flags |
| --- | --- | --- | --- | --- | --- |
| Norman Powell | low_usage_spacer | low-usage spacer | False | True | maxey_usage_overlap |
| Stephon Castle | bench_creator | bench creator | False | True | maxey_usage_overlap |
| Collin Sexton | bench_creator | bench creator | False | True | maxey_usage_overlap |
| Jeremiah Fears | bench_creator | bench creator | False | True | maxey_usage_overlap |
| Maxime Raynaud | matchup_big | non-Embiid center minutes, backup center, or matchup big | False | True | normal_starting_center_slot_blocked_by_embiid |
| Deandre Ayton | matchup_big | non-Embiid center minutes, backup center, or matchup big | False | True | normal_starting_center_slot_blocked_by_embiid |
| Wendell Carter Jr. | matchup_big | non-Embiid center minutes, backup center, or matchup big | False | True | normal_starting_center_slot_blocked_by_embiid |
| Dillon Brooks | low_usage_spacer | low-usage spacer | False | True | maxey_usage_overlap |
| Bennedict Mathurin | point_of_attack_defender | point-of-attack defender next to Maxey | True | True | maxey_usage_overlap |
| Derik Queen | matchup_big | non-Embiid center minutes, backup center, or matchup big | False | True | normal_starting_center_slot_blocked_by_embiid |
| Nikola Vučević | matchup_big | non-Embiid center minutes, backup center, or matchup big | False | True | normal_starting_center_slot_blocked_by_embiid |
| Jarrett Allen | matchup_big | non-Embiid center minutes, backup center, or matchup big | False | True | normal_starting_center_slot_blocked_by_embiid |
| Russell Westbrook | bench_creator | bench creator | False | True | maxey_usage_overlap |
| Donovan Clingan | matchup_big | non-Embiid center minutes, backup center, or matchup big | False | True | normal_starting_center_slot_blocked_by_embiid |
| Kyle Filipowski | matchup_big | non-Embiid center minutes, backup center, or matchup big | False | True | normal_starting_center_slot_blocked_by_embiid |

## No Clear Role Examples

| Player | Primary Slot | Role | Starter | Playoff | Flags |
| --- | --- | --- | --- | --- | --- |
| Obi Toppin | no_clear_role | no clear Sixers role from current evidence | False | False | no_clear_role |
| Ty Jerome | no_clear_role | no clear Sixers role from current evidence | False | False | maxey_usage_overlap, no_clear_role |
| Dejounte Murray | no_clear_role | no clear Sixers role from current evidence | False | False | maxey_usage_overlap, no_clear_role |
| Cormac Ryan | no_clear_role | no clear Sixers role from current evidence | False | False | candidate_status_manual_review_required, no_clear_role |
| D'Angelo Russell | no_clear_role | no clear Sixers role from current evidence | False | False | maxey_usage_overlap, no_clear_role |
| Tyson Etienne | no_clear_role | no clear Sixers role from current evidence | False | False | candidate_status_manual_review_required, no_clear_role |
| Asa Newell | no_clear_role | no clear Sixers role from current evidence | False | False | no_clear_role |
| Blake Hinson | no_clear_role | no clear Sixers role from current evidence | False | False | candidate_status_manual_review_required, no_clear_role |
| Jamal Cain | no_clear_role | no clear Sixers role from current evidence | False | False | candidate_status_manual_review_required, no_clear_role |
| Nick Smith Jr. | no_clear_role | no clear Sixers role from current evidence | False | False | no_clear_role |
| LJ Cryer | no_clear_role | no clear Sixers role from current evidence | False | False | candidate_status_manual_review_required, no_clear_role |
| Marcus Sasser | no_clear_role | no clear Sixers role from current evidence | False | False | no_clear_role |
| Cam Whitmore | no_clear_role | no clear Sixers role from current evidence | False | False | no_clear_role |
| Joan Beringer | no_clear_role | no clear Sixers role from current evidence | False | False | no_clear_role |
| Chaney Johnson | no_clear_role | no clear Sixers role from current evidence | False | False | candidate_status_manual_review_required, no_clear_role |

## Rules

- Centers are not projected as normal starters because Embiid owns that slot.
- Double-big roles require shooting plus mobility/defensive evidence.
- Regular-season depth alone is not a priority playoff role.