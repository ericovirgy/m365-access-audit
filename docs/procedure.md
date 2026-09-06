# Access review procedure

This is a reusable procedure for the periodic access audit of a Microsoft 365 tenant. It describes what to review, who does what, how often, and what evidence to keep. It is written so that any organisation with a small IT function can adopt it as is, adjusting only the names and the periodicity.

## 1. Purpose

The audit verifies, at regular intervals, that every account in the tenant still corresponds to a real person or service that needs access, that the permissions and roles assigned match current responsibilities, and that licences are not being consumed by accounts that no longer need them. The output is a reviewable report with a signed record that the review happened. Access that is not reviewed drifts: people leave, contractors roll off, roles accumulate. This procedure is the control that stops that drift.

## 2. Scope

- All user accounts in the tenant: members and guests, enabled and disabled.
- Membership of the privileged directory roles listed in the tool, plus any role the organisation adds to that list.
- Licence assignments against active need.
- Group membership of groups that grant access to something (file shares, applications, teams). Groups that are purely distribution lists are optional.

Out of scope for this procedure: Conditional Access policies, PIM configuration, device compliance, application-level permissions. They can be appended later; do not let their absence delay the review of accounts and roles.

## 3. Roles

Three roles, which may be held by the same person only when no alternative exists, and in that case the approver must be outside IT.

- **System owner**: the person accountable for the tenant. Typically the IT administrator or head of IT. Maintains this procedure, runs the tool, prepares the report, executes approved changes.
- **Reviewer**: goes through every finding, decides per finding: keep, change, or remove. Must not be the person who requested the access being reviewed. In a sole-administrator organisation, the reviewer is the administrator and the approver is the manager the administrator reports to.
- **Approver**: formally accepts the review outcome and the resulting action list. Signs the report. Owns the escalation if actions are not executed.

## 4. Periodicity

- Quarterly is the minimum. Monthly is recommended while the tenant is young, after a reorganisation, or whenever the previous review produced more than a handful of removals.
- Run the review in the first week of the month or quarter, so the evidence is dated inside the period it covers.
- An off-cycle review is mandatory after any of the following: departure of a privileged role member, a suspected account compromise, or a change of the system owner.

## 5. Inputs

- The report produced by `m365-access-audit` (`report-<timestamp>.md` and `findings-<timestamp>.csv`) for the current run.
- The previous signed report, for comparison.
- Current organisational information: who is employed, who is a contractor, contract end dates. The reviewer needs a source of truth for who should have access; the tool cannot provide that.

## 6. Steps

1. **Collect.** Run the tool against the tenant and store the report. Do not fix anything before the report is produced: the report must reflect the state of the tenant, not the state after partial cleanup.
2. **Compare.** Open the previous signed report side by side. Note accounts that disappeared (confirm they were deprovisioned properly) and new privileged members (confirm who approved them).
3. **Review every finding.** Work through the checklist in the report top to bottom. For each line, tick it only when a decision was made and recorded. Section 7 lists the decision to take per finding type.
4. **Record decisions.** In the copy of the report, next to each finding, write the decision and, when the answer is "keep", the reason. "Keep" without a reason is not a decision.
5. **Get sign-off.** Send the completed report to the approver. The approver signs the sign-off block after challenging at least the "keep" decisions on privileged roles.
6. **Execute changes.** The system owner applies the approved removals and changes within five working days. Changes to privileged roles are executed first.
7. **Close.** File the signed report and the change log together. Re-run the tool after execution; the re-run should show the removals. Attach the re-run report to the file as proof of execution.

## 7. What to do with each finding type

- **INACTIVE** (enabled account, no sign-in above threshold): contact the account owner or their manager. If the person left, disable the account the same day and remove licences. If the person is on extended leave, record that and keep. If nobody knows the account, disable it.
- **DISABLED_WITH_LICENCE** (disabled account still licensed): reclaim the licence in the Microsoft 365 admin center. A disabled account must not consume a licence. This recovers licence cost with no impact on anyone; execute immediately.
- **LICENSED_NEVER_SIGNED_IN** (licensed, no sign-in ever, account older than 30 days): confirm the account is expected, for example a staged onboarding. If it is not, disable it and reclaim the licence. If it happens every month for the same provisioning process, fix the process.
- **PRIVILEGED_ROLE_MEMBER** (member of a privileged role, always listed): for each name, answer: does this person need this role today? Standing privileged access is the exception, not the rule. Remove roles that are no longer needed; where the platform allows, replace standing access with just-in-time activation. A member whose account is also inactive (severity high) is reviewed the same day the report is produced.
- **STALE_GUEST** (guest, no sign-in above 180 days): remove the guest if the collaboration has ended, or ask the sponsoring employee to confirm it is still active. Guests without an identifiable sponsor are removed.
- **ORPHANED_ADMIN** (disabled account still holding an admin role): remove the role assignment immediately, before the review cycle closes. A disabled account holding a role is a finding to fix, not to discuss.

## 8. Evidence to retain

Keep, for each review cycle:

- The report as produced by the tool, unmodified.
- The completed report with decisions, ticked checklist and signed sign-off block.
- The re-run report after execution of changes.
- The change log: date, account, what changed, who approved.

Retain for at least two years, or the period your sector or regulator requires. Store the files where they cannot be edited after the fact; a dedicated read-only document library or an archive directory works. The CSV is the machine-readable record: keep it next to the report.

## 9. Sign-off block

Copy this block into the completed report before signing.

```
Review period: ______________________
Report file:   ______________________

Reviewer
  Name:      ______________________
  Date:      ______________________
  Signature: ______________________
  Statement: I reviewed every finding in this report and recorded a decision for each.

Approver
  Name:      ______________________
  Date:      ______________________
  Signature: ______________________
  Statement: I accept the decisions recorded above and the resulting action list.
```
