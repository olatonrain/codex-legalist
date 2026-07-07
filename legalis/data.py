"""
legalis/data.py
───────────────
Static demo-case data and agent styling constants.
Pulled out of server.py so the server layer stays thin.
"""

# ── Agent display config ─────────────────────────────────────────────────────
AGENT_STYLE: dict[str, tuple[str, str]] = {
    "Bailiff":     ("BL", "av-system"),
    "Judge":       ("JD", "av-judge"),
    "Prosecutor":  ("PR", "av-prosecutor"),
    "Defense":     ("DF", "av-defense"),
    "Witness":     ("WS", "av-witness"),
    "Magistrate":  ("MG", "av-magistrate"),
    "Foreperson":  ("FP", "av-foreperson"),
    "Juror":       ("JR", "av-juror"),
    "Fact Checker": ("FC", "av-checker"),
    "System":      ("—",  "av-system"),
}

AGENT_NAME_COLOR: dict[str, str] = {
    "Judge":        "#ff9f0a",
    "Prosecutor":   "#ff453a",
    "Defense":      "#0a84ff",
    "Defense Counsel": "#0a84ff",
    "Witness":      "#30d158",
    "Foreperson":   "#bf5af2",
    "Juror":        "#5ac8fa",
    "Fact Checker": "#ff6961",
    "Magistrate":   "#ff9f0a",
    "Bailiff":      "#c9a84c",
    "System":       "#48484a",
}

# ── Demo trial scripts ────────────────────────────────────────────────────────
DEMO_CASES: dict[str, dict] = {
    "theft": {
        "title": "State v. Marcus Webb — Grand Theft Auto",
        "jurisdiction": "United States · NY Southern District",
        "description": (
            "The defendant, Marcus Webb, is charged with stealing a 2024 Tesla Model Y "
            "from outside 'The Blue Note' jazz bar on March 14th. A parking-lot camera "
            "captured a figure matching Webb's build at 11:47 PM. Webb claims he was "
            "inside until midnight; his alibi is bartender Sarah Lin."
        ),
        "questions": [
            "Was the security footage clear enough to identify facial features?",
            "Did Sarah Lin have an unobstructed view of Webb at 11:47 PM?",
            "Were the defendant's fingerprints found on the vehicle?",
            "Did Webb have a prior relationship with the vehicle's owner?",
            "Was any stolen property recovered from Webb's residence?",
        ],
        "trial_script": [
            # ════════════════ PHASE 1: DISCOVERY ════════════════
            {"agent": "Bailiff",    "text": "All rise. The Honorable Justice Vance presiding. The court is now in session for the Discovery Disclosure phase.",                                                                      "phase": "Discovery"},
            {"agent": "Judge",      "text": "Be seated. State versus Marcus Webb — Grand Theft Auto in the First Degree. We proceed with discovery disclosure. Mr. Mercer.",                                                      "phase": "Discovery"},
            {"agent": "Prosecutor", "text": "The People disclose: (1) Parking-lot camera footage, Exhibit A, timestamped 11:47 PM March 14th; (2) Vehicle owner statement confirming locked and parked at 9:00 PM; (3) Officer Daniels' incident report.", "phase": "Discovery"},
            {"agent": "Defense",    "text": "The defense discloses: (1) Sworn affidavit from bartender Sarah Lin placing Webb inside The Blue Note bar at 11:30 PM and near midnight; (2) Bar credit card receipt showing Webb's tab active at 11:42 PM.", "phase": "Discovery"},
            {"agent": "Judge",      "text": "Disclosure is complete. Proceed to pre-trial motions.",                                                                                                                               "phase": "Discovery"},

            # ════════════════ PHASE 2: PRE-TRIAL MOTIONS ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to pre-trial motions.",                                                                                                                                       "phase": "Motions"},
            {"agent": "Judge",      "text": "Defense counsel, your motion to suppress the parking-lot footage. State your grounds.",                                                                                                  "phase": "Motions"},
            {"agent": "Defense",    "text": "Your Honor, the footage is 480p resolution. The figure's face is not identifiable. Under FRE 403, the prejudicial effect of a shadowy silhouette substantially outweighs any probative value. No eyewitness can verify it is Webb.", "phase": "Motions"},
            {"agent": "Prosecutor", "text": "The figure's height, build, and gait match the defendant. The footage is time-stamped. The People can cross-reference with the defendant's own clothing. This is not prejudice — it is evidence.", "phase": "Motions"},
            {"agent": "Judge",      "text": "Motion to suppress is DENIED. The deficiencies in quality go to weight, not admissibility. The defense may cross-examine on the footage's limitations. FRE 401.",                      "phase": "Motions"},
            {"agent": "Prosecutor", "text": "The People move to introduce evidence of three prior auto thefts in a three-block radius during the same week, showing pattern, under FRE 404(b).",                                    "phase": "Motions"},
            {"agent": "Defense",    "text": "Objection. No evidence links Webb to those thefts. This is pure character evidence designed to paint my client as a criminal. Highly prejudicial.",                                    "phase": "Motions"},
            {"agent": "Judge",      "text": "Motion DENIED. Without any nexus to the defendant, the prior thefts are irrelevant and would be unfairly prejudicial. FRE 404(b). Stricken.",                                           "phase": "Motions"},

            # ════════════════ PHASE 3: OPENING STATEMENTS ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to opening statements.",                                                                                                                                      "phase": "Opening"},
            {"agent": "Judge",      "text": "Mr. Mercer — your opening statement.",                                                                                                                                                    "phase": "Opening"},
            {"agent": "Prosecutor", "text": "Ladies and gentlemen — at 11:47 PM on March 14th, a 2024 Tesla Model Y was stolen from outside The Blue Note jazz bar. The evidence will show that Marcus Webb was the man behind that theft. Security camera footage captured a figure matching Webb's height and build at the vehicle at precisely the time of the theft. Webb claims he was inside the bar — but his alibi witness, bartender Sarah Lin, admits she cannot account for his whereabouts during the critical window. The prosecution will prove beyond a reasonable doubt that Marcus Webb committed Grand Theft Auto in the First Degree.", "phase": "Opening"},
            {"agent": "Judge",      "text": "Defense counsel.",                                                                                                                                                                        "phase": "Opening"},
            {"agent": "Defense",    "text": "Members of the jury — the prosecution asks you to convict on a grainy shadow. Let me tell you what they do not have: No fingerprints on the vehicle. No DNA evidence. No stolen property recovered from Webb's residence. No eyewitness who can identify his face. Their entire case rests on a 480p camera that captured a silhouette — and a bartender who confirms Webb was in the bar at the time. The standard is proof beyond a reasonable doubt. A silhouette is not proof. You must find Marcus Webb Not Guilty.", "phase": "Opening"},

            # ════════════════ PHASE 4: EVIDENCE PRESENTATION ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to evidence presentation.",                                                                                                                                   "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "The People submit Exhibit A: parking-lot camera footage, timestamped 11:47 PM, March 14th, showing a figure approaching the Tesla.",                                                      "phase": "Evidence"},
            {"agent": "Defense",    "text": "Objection. FRE 403 — the footage is 480p and the figure's face is not identifiable. It is more prejudicial than probative. The jury cannot distinguish Webb from any random person.",     "phase": "Evidence"},
            {"agent": "Judge",      "text": "Overruled. The resolution is a matter of weight for the jury. The timestamp and physical characteristics are probative. FRE 401. Exhibit A admitted.",                                    "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "The People submit Exhibit B: vehicle owner statement confirming the Tesla was locked, armed, and parked at 9:00 PM. The owner returned at 12:30 AM to find the space empty.",            "phase": "Evidence"},
            {"agent": "Judge",      "text": "Exhibit B admitted without objection.",                                                                                                                                                   "phase": "Evidence"},
            {"agent": "Defense",    "text": "The defense submits Exhibit C: bar credit card receipt showing Webb's tab was active at 11:42 PM — five minutes before the alleged theft.",                                               "phase": "Evidence"},
            {"agent": "Judge",      "text": "Exhibit C admitted without objection.",                                                                                                                                                   "phase": "Evidence"},

            # ════════════════ PHASE 5: WITNESS EXAMINATION ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to witness examination.",                                                                                                                                    "phase": "Witness"},

            # --- Officer Daniels ---
            {"agent": "Prosecutor", "text": "The People call Officer Daniels. Officer — describe what you observed at the scene.",                                                                                                    "phase": "Witness"},
            {"agent": "Witness",    "text": "I arrived at 12:15 AM. The parking space was empty. I reviewed the footage on-site — a figure matching Webb's height and build was near the vehicle at 11:47 PM. The timestamp is continuous — no gaps in the recording.", "phase": "Witness"},
            {"agent": "Defense",    "text": "Officer, you cannot identify the face in the footage — correct?",                                                                                                                          "phase": "Witness"},
            {"agent": "Witness",    "text": "Correct. The face is not clearly visible. But the build, height, and gait pattern are consistent with booking photos of the defendant.",                                                  "phase": "Witness"},
            {"agent": "Defense",    "text": "This parking lot serves a jazz bar on a Friday night. How many people approximately match Webb's height and build in a city of eight million?",                                           "phase": "Witness"},
            {"agent": "Witness",    "text": "Many could. I cannot give a number.",                                                                                                                                                     "phase": "Witness"},
            {"agent": "Prosecutor", "text": "One question on redirect, Officer. Does the footage show anyone ELSE near that Tesla at 11:47 PM?",                                                                                       "phase": "Witness"},
            {"agent": "Witness",    "text": "No. Only one figure approaches the vehicle at that time. No one else is visible in the frame.",                                                                                           "phase": "Witness"},
            {"agent": "Fact Checker", "text": "✓ Response consistent with footage review notes. No other individuals visible in timestamped frames.",                                                                                  "phase": "Witness"},

            # --- Sarah Lin (alibi) ---
            {"agent": "Defense",    "text": "The defense calls Sarah Lin. Ms. Lin — you are a bartender at The Blue Note. Was Marcus Webb in the bar at 11:47 PM on March 14th?",                                                      "phase": "Witness"},
            {"agent": "Witness",    "text": "Yes. I served him a whiskey sour around 11:30 PM. He settled his tab at 11:42 PM — I have the receipt. He was sitting at the bar talking with other regulars.",                          "phase": "Witness"},
            {"agent": "Prosecutor", "text": "Ms. Lin — it was a busy Friday night. You were serving dozens of customers. Could you have lost sight of him for ten or fifteen minutes?",                                                "phase": "Witness"},
            {"agent": "Witness",    "text": "It was very busy, yes. The bar seats forty people. I can't watch everyone every second. But the receipt shows he was active on his tab at 11:42 PM.",                                    "phase": "Witness"},
            {"agent": "Prosecutor", "text": "The tab receipt shows a transaction time. It does not show his physical location. The parking lot is 90 seconds from the bar's entrance. He could have walked out, committed the theft, and returned unnoticed — correct?", "phase": "Witness"},
            {"agent": "Witness",    "text": "...I suppose it's physically possible, yes. The bar has a side exit.",                                                                                                                    "phase": "Witness"},
            {"agent": "Fact Checker", "text": "✓ Testimony consistent with deposition. Witness acknowledges gaps in observation.",                                                                                                    "phase": "Witness"},

            # ════════════════ PHASE 6: REBUTTAL EVIDENCE ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to rebuttal evidence.",                                                                                                                                         "phase": "Rebuttal"},
            {"agent": "Judge",      "text": "Prosecution — rebuttal?",                                                                                                                                                                  "phase": "Rebuttal"},
            {"agent": "Prosecutor", "text": "Your Honor, the defense introduced a credit card receipt. But we note the receipt shows a tab closing — not a presence confirmation. A tab can be closed by anyone. And we submit — through Officer Daniels — that the 11:47 PM timestamp on the footage is independently verified by the camera's NTP server. The timeline is exact.", "phase": "Rebuttal"},
            {"agent": "Judge",      "text": "Defense — surrebuttal?",                                                                                                                                                                   "phase": "Rebuttal"},
            {"agent": "Defense",    "text": "The receipt is a machine-generated timestamp from a POS system, independently verified by the bar's transaction log. It carries the same weight as any digital record. My client closed his own tab. The prosecution cannot prove otherwise.", "phase": "Rebuttal"},
            {"agent": "Fact Checker", "text": "✓ Both exhibits are independently timestamped. Conflict is a matter for the jury.",                                                                                                      "phase": "Rebuttal"},

            # ════════════════ PHASE 7: CLOSING ARGUMENTS ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to closing arguments.",                                                                                                                                         "phase": "Closing"},
            {"agent": "Prosecutor", "text": "Camera places a figure matching the defendant at the scene, at the exact time of the theft. No one else is visible. The alibi witness admits to gaps. The bar receipt proves a transaction — not a location. The evidence points to one conclusion.", "phase": "Closing"},
            {"agent": "Defense",    "text": "A shadow is not proof beyond a reasonable doubt. No fingerprints. No DNA. No property recovered. No eyewitness identification. The camera is 480p — it cannot identify a face. The bartender confirms Webb was in the bar. The receipt proves activity at 11:42 PM. Reasonable doubt exists at every turn. You must find Marcus Webb Not Guilty.", "phase": "Closing"},

            # ════════════════ PHASE 8: JURY INSTRUCTIONS ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to jury instructions.",                                                                                                                                         "phase": "Jury Instructions"},
            {"agent": "Judge",      "text": "Members of the jury — the defendant is charged with Grand Theft Auto in the First Degree under New York Penal Law 155.42. To find the defendant guilty, you must find: (1) the defendant took a motor vehicle valued over $50,000, (2) belonging to another person, (3) with intent to permanently deprive the owner of it. The prosecution bears the burden of proof beyond a reasonable doubt. Circumstantial evidence may support a conviction only if it excludes every reasonable hypothesis of innocence. If you have a reasonable doubt, you must acquit.", "phase": "Jury Instructions"},

            # ════════════════ PHASE 9: JURY DELIBERATION ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to jury deliberation.",                                                                                                                                         "phase": "Jury Deliberation"},
            {"agent": "Foreperson", "text": "Each juror, please state your initial position.",                                                                                                                                           "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #1 (Analytical): Not Guilty. The footage cannot identify a face. No forensic evidence exists. The prosecution relies entirely on inference from proximity.",                          "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #2 (Empathetic): Not Guilty. The bartender was convincing. The receipt is hard physical proof of his presence in the bar.",                                                           "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #3 (Skeptical): Guilty. The bar was busy — she could have lost track. The camera puts someone his exact size at the vehicle. The timing is too precise.",                             "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #4 (Pragmatic): Not Guilty. Too many gaps. No physical evidence. The standard is beyond reasonable doubt, and I have doubt.",                                                          "phase": "Jury Deliberation"},
            {"agent": "Foreperson", "text": "Round 1: 3 Not Guilty, 1 Guilty. Juror #3 — please elaborate.",                                                                                                                            "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #3: Circumstantial is still evidence. The timing and the camera together make it unlikely it's a coincidence. But the judge said circumstantial must exclude every reasonable hypothesis — and 'someone else matching his build' is a reasonable hypothesis. I'll change my vote.", "phase": "Jury Deliberation"},
            {"agent": "Foreperson", "text": "Round 2: 4 Not Guilty, 0 Guilty. Unanimous verdict reached.",                                                                                                                              "phase": "Jury Deliberation"},

            # ════════════════ PHASE 10: SHADOW JURY ════════════════
            {"agent": "Bailiff",    "text": "The shadow jury has convened for analysis.",                                                                                                                                               "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 1: The footage is too low-resolution to identify anyone. No forensic links to Webb. The bartender's credit card receipt is independently verifiable. [Vote: Not Guilty]",      "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 2: The defense successfully established that 'someone with similar build' is a reasonable alternative. The prosecution did not exclude that hypothesis. [Vote: Not Guilty]",    "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 3: The alibi has gaps, but suspicion is not proof. The camera at 480p is effectively worthless for identification. Justice requires more. [Vote: Not Guilty]",               "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 4: The prosecution's case is entirely circumstantial. No DNA, no fingerprints, no recovery of property. The standard of beyond reasonable doubt is not met. [Vote: Not Guilty]", "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 5: Timing is suspicious, but the bar receipt at 11:42 PM creates a very narrow window for the crime. Reasonable doubt exists. [Vote: Not Guilty]",                            "phase": "Shadow Jury"},
            {"agent": "Bailiff",    "text": "The shadow jury has completed its analysis.",                                                                                                                                              "phase": "Shadow Jury"},

            # ════════════════ PHASE 11: VERDICT (Not Guilty → no sentencing) ════════════════
            {"agent": "Bailiff",    "text": "All rise for the reading of the verdict.",                                                                                                                                                 "phase": "Verdict"},
            {"agent": "Judge",      "text": "On the charge of Grand Theft Auto in the First Degree, the defendant Marcus Webb is found NOT GUILTY. The defendant is free to go.",                                                        "phase": "Verdict"},

            # ════════════════ PHASE 12: COURT REPORTER ════════════════
            {"agent": "Bailiff",    "text": "Case 24-CR-0081 — State of New York versus Marcus Webb — is concluded. The trial record shall be certified by the court reporter.",                                                        "phase": "Court Reporter Log"},
            {"agent": "System",     "text": "[Court Reporter Log: Complete trial record compiled. Case 24-CR-0081. Verdict: NOT GUILTY. Transcript includes 3 exhibits, 2 witnesses, 2 pre-trial motions, 1 objection ruling, 6-phase trial, 5 shadow juror analyses.]", "phase": "Court Reporter Log"},

            # ════════════════ ADJOURNED ════════════════
            {"agent": "Bailiff",    "text": "All charges have been adjudicated. This court is adjourned.",                                                                                                                               "phase": "Adjourned"},
        ],
        "verdict": "NOT GUILTY",
        "win_probability": 0.32,
        "sensitivity": "If fingerprints had been found → Prosecution win probability rises to 78%",
        "shadow_jury_narrative": [
            {"name": "Shadow Juror 1", "content": "The footage is too grainy to identify the defendant with certainty. No forensic evidence links Webb to the vehicle. The bartender's testimony creates reasonable doubt. [Vote: Not Guilty]"},
            {"name": "Shadow Juror 2", "content": "While the figure matches Webb's build, that is not identification. No fingerprints, no DNA, no recovered property. The prosecution has not met its burden. [Vote: Not Guilty]"},
            {"name": "Shadow Juror 3", "content": "The alibi is weak — a busy bar with gaps in memory. But circumstantial evidence alone cannot convict beyond reasonable doubt. [Vote: Not Guilty]"},
            {"name": "Shadow Juror 4", "content": "Security footage at 480p is nearly useless for facial identification. Without physical evidence, this case is speculation. [Vote: Not Guilty]"},
            {"name": "Shadow Juror 5", "content": "The timing is suspicious, but suspicion is not proof. The defense raised sufficient doubt. [Vote: Not Guilty]"},
        ],
    },

    "contract": {
        "title": "Nexus Corp. v. Aether Labs — NDA Breach",
        "jurisdiction": "United States · Delaware",
        "description": (
            "Nexus Corp. alleges Aether Labs violated an NDA by sharing proprietary battery "
            "schematics with PowerCell Inc. Aether Labs claims the shared information was "
            "independently developed and not within scope of the agreement."
        ),
        "questions": [
            "Does the NDA explicitly define 'proprietary battery technology'?",
            "Did Aether Labs document independent research predating the NDA?",
            "Was there a formal data-sharing agreement with PowerCell Inc.?",
            "Did a Nexus engineer confirm the shared schematics match their IP?",
            "What was the quantified financial impact to Nexus Corp.?",
        ],
        "trial_script": [
            # ════════════════ PHASE 1: DISCOVERY ════════════════
            {"agent": "Bailiff",    "text": "All rise. The Honorable Justice Park presiding. The court is now in session for the Discovery Disclosure phase.",                                                                  "phase": "Discovery"},
            {"agent": "Judge",      "text": "Be seated. Nexus Corporation versus Aether Laboratories — alleged breach of Non-Disclosure Agreement. Plaintiff's counsel — your disclosure.",                                   "phase": "Discovery"},
            {"agent": "Prosecutor", "text": "The plaintiff discloses: (1) The signed NDA between Nexus Corp. and Aether Labs, dated January 15, 2023; (2) Email from Aether CTO to PowerCell attaching 'NX-Battery-Specs-v3.pdf'; (3) Dr. Helen Marsh's comparative materials analysis report showing 94% structural match; (4) Nexus NX-7 battery schematics shared with Aether under the NDA.", "phase": "Discovery"},
            {"agent": "Defense",    "text": "Aether Labs discloses: (1) Internal research logs predating the NDA showing independent cathode development; (2) Expert report by Dr. Raj Mehta, independent materials scientist, concluding cathode layering is standard industry practice; (3) Correspondence logs showing all public-domain information shared with PowerCell.", "phase": "Discovery"},
            {"agent": "Judge",      "text": "Disclosure is complete. The court notes competing expert reports. Proceed to pre-trial motions.",                                                                                  "phase": "Discovery"},

            # ════════════════ PHASE 2: PRE-TRIAL MOTIONS ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to pre-trial motions.",                                                                                                                                "phase": "Motions"},
            {"agent": "Judge",      "text": "Defense counsel — your motion to exclude the email as insufficient proof.",                                                                                                        "phase": "Motions"},
            {"agent": "Defense",    "text": "Your Honor, the email's file name 'NX-Battery-Specs-v3.pdf' is not proof that the file contains Nexus IP. The plaintiff has not produced the actual attached file. A file name is hearsay and is insufficient to establish content under FRE 1002 — the Best Evidence Rule.", "phase": "Motions"},
            {"agent": "Prosecutor", "text": "The email is a business record of Aether Labs' own communication. Aether's CTO sent it. Aether's email server generated it. The People are not offering the file name to prove the file's contents — we are offering it to prove Aether knowingly used Nexus's internal designation. That is not hearsay.", "phase": "Motions"},
            {"agent": "Judge",      "text": "Motion DENIED. The email is admitted as a party-opponent statement under FRE 801(d)(2) — it is Aether's own communication. The file name is not being offered for its truth but to show Aether's knowledge and frame of mind. The defense may argue weight.", "phase": "Motions"},
            {"agent": "Prosecutor", "text": "The plaintiff moves for summary judgment under FRCP 56. The NDA is clear, the email connects Aether to PowerCell, and Dr. Marsh's report shows 94% match. No genuine dispute of material fact.", "phase": "Motions"},
            {"agent": "Defense",    "text": "Aether opposes. Material facts are genuinely disputed: whether the NDA covers cathode layering as 'proprietary technology,' whether Aether independently developed that layering before the NDA, and whether the 94% match reflects coincidence in an iterative field. These are jury questions.", "phase": "Motions"},
            {"agent": "Judge",      "text": "Summary judgment DENIED. The scope of 'proprietary technology' under the NDA and the independence of Aether's development are disputed facts for the jury to resolve.",                "phase": "Motions"},

            # ════════════════ PHASE 3: OPENING STATEMENTS ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to opening statements.",                                                                                                                                "phase": "Opening"},
            {"agent": "Judge",      "text": "Plaintiff's counsel — opening statement, please.",                                                                                                                                    "phase": "Opening"},
            {"agent": "Prosecutor", "text": "Ladies and gentlemen — Nexus Corp. entrusted Aether Laboratories with its most valuable intellectual property: a next-generation battery cathode design that took four years and eighteen million dollars to develop. They signed an NDA explicitly protecting 'all technical specifications shared during the partnership.' Within six months of receiving those specifications, Aether's CTO emailed a file named after Nexus's internal designation — 'NX-Battery-Specs-v3.pdf' — to PowerCell, a Nexus competitor. Dr. Helen Marsh, Nexus's lead materials engineer, will testify that PowerCell's subsequent product is a 94% structural match to the NX-7 design. The evidence proves Aether breached the NDA. We ask you to find Aether liable and award damages.", "phase": "Opening"},
            {"agent": "Judge",      "text": "Defense counsel.",                                                                                                                                                                    "phase": "Opening"},
            {"agent": "Defense",    "text": "The plaintiff cannot prove the email attachment contained anything proprietary because they never produced the file. A file name is not a blueprint. Cathode layering — the technique at the center of this case — has been published in open-access materials science journals since 2009. Aether's internal research logs predate the NDA by eighteen months. A 94% match across two products in an industry where every manufacturer optimizes the same few parameters is not theft — it is parallel evolution. The NDA does not cover generally known engineering principles, which is exactly what cathode layering is. You must find Aether Labs Not Liable.", "phase": "Opening"},

            # ════════════════ PHASE 4: EVIDENCE PRESENTATION ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to evidence presentation.",                                                                                                                            "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "Plaintiff submits Exhibit A: the signed Non-Disclosure Agreement between Nexus Corp. and Aether Labs, dated January 15, 2023. Clause 3.1: 'All technical specifications, schematics, test data, and manufacturing processes shared during the partnership are confidential and shall not be disclosed to any third party.'", "phase": "Evidence"},
            {"agent": "Judge",      "text": "Exhibit A admitted without objection.",                                                                                                                                               "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "Plaintiff submits Exhibit B: email from Aether CTO Samir Patel to PowerCell CTO Gina Torres, dated July 8, 2023, attaching a file named 'NX-Battery-Specs-v3.pdf.' Subject line: 'Per our discussion.'", "phase": "Evidence"},
            {"agent": "Defense",    "text": "Objection. The file name alone does not prove the contents are Nexus IP. Under FRE 1002 — the Best Evidence Rule — the original file must be produced to prove its content. An email with a filename is insufficient.", "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "The email is offered as a party-opponent statement under FRE 801(d)(2), not to prove the file's contents. The file name is relevant to show Aether's knowledge of Nexus's internal designation system.", "phase": "Evidence"},
            {"agent": "Judge",      "text": "Sustained in part. The email is admitted as a party-opponent statement. The filename may be considered for what it shows about Aether's awareness — not for the truth of the file's contents. FRE 1002 remains applicable to the attachment itself. The jury will be so instructed.", "phase": "Evidence"},
            {"agent": "Defense",    "text": "The defense submits Exhibit C: Aether's internal research logs, dated April 2021 through January 2023, documenting independent cathode layering experiments at Aether's Fremont facility.", "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "Objection. Foundation — the defense has not established that these logs were created contemporaneously with the experiments. No witness has authenticated them.",                       "phase": "Evidence"},
            {"agent": "Defense",    "text": "Dr. Mehta will authenticate these logs during his testimony. They are date-stamped in Aether's laboratory information management system.",                                              "phase": "Evidence"},
            {"agent": "Judge",      "text": "Conditionally admitted pending Dr. Mehta's authentication. FRE 104(b). Exhibit C admitted subject to connection.",                                                                     "phase": "Evidence"},

            # ════════════════ PHASE 5: WITNESS EXAMINATION ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to witness examination.",                                                                                                                               "phase": "Witness"},

            # --- Expert: Dr. Helen Marsh (Nexus materials engineer) ---
            {"agent": "Prosecutor", "text": "The plaintiff calls Dr. Helen Marsh, Lead Materials Engineer at Nexus Corp. Dr. Marsh — please state your qualifications for the court.",                                           "phase": "Witness"},
            {"agent": "Witness",    "text": "I hold a Ph.D. in Materials Science from MIT. I have 14 years of experience in battery cathode engineering, hold 7 patents in lithium-ion cathode architecture, and have published 22 peer-reviewed papers on solid-state battery materials. I led the NX-7 cathode design team at Nexus.", "phase": "Witness"},
            {"agent": "Judge",      "text": "Defense — would you like to voir dire the witness on her qualifications?",                                                                                                          "phase": "Witness"},
            {"agent": "Defense",    "text": "Dr. Marsh — your 7 patents are held by Nexus Corp., not by you personally. And your published papers focus on solid-state batteries, not the lithium-ion technology at issue here. Are you qualified specifically to assess cathode layering similarity in lithium-ion cells?", "phase": "Witness"},
            {"agent": "Witness",    "text": "My doctoral thesis was on lithium-ion cathode deposition morphology. I have been working exclusively on lithium-ion cathodes for eight of my fourteen years at Nexus. Solid-state is a more recent interest — my core expertise is lithium-ion. My patents cover lithium-ion cathode architecture.", "phase": "Witness"},
            {"agent": "Defense",    "text": "No further questions on qualifications, Your Honor.",                                                                                                                               "phase": "Witness"},
            {"agent": "Judge",      "text": "The court qualifies Dr. Marsh as an expert in battery cathode engineering under FRE 702. You may proceed.",                                                                            "phase": "Witness"},

            # --- Direct: Dr. Marsh ---
            {"agent": "Prosecutor", "text": "Dr. Marsh — describe your analysis comparing PowerCell's product to the NX-7 schematics shared with Aether Labs.",                                                                  "phase": "Witness"},
            {"agent": "Witness",    "text": "I performed a cross-sectional analysis of PowerCell's PC-900 cathode using scanning electron microscopy and X-ray diffraction. The cathode layering pattern — specifically the thickness ratios between the lithium cobalt oxide layer, the manganese spinel interlayer, and the carbon coating — is a 94% structural match to our NX-7 design. The dopant sequence — nickel followed by aluminum at specific concentration gradients — is identical to our proprietary formulation.", "phase": "Witness"},
            {"agent": "Prosecutor", "text": "Could these results be a coincidence? Could two teams independently develop the same structure?",                                                                                  "phase": "Witness"},
            {"agent": "Witness",    "text": "The general concept of cathode layering is known. But the specific combination of three thickness ratios plus the exact dopant sequence creates a unique signature. The probability of two independent teams arriving at this exact combination — across four independent variables — is less than 0.001%.", "phase": "Witness"},

            # --- Cross: Dr. Marsh ---
            {"agent": "Defense",    "text": "Dr. Marsh — your 0.001% probability assumes each variable is independent. But in layered cathode design, these variables are interdependent — a change in one layer's thickness affects the optimal thickness of adjacent layers. Your independence assumption is wrong, isn't it?", "phase": "Witness"},
            {"agent": "Witness",    "text": "The variables do interact, yes. That makes independent coincidence less likely, not more — because the interaction constraints narrow the viable design space. The 94% match is even more significant when you account for inter-variable dependencies.", "phase": "Witness"},
            {"agent": "Defense",    "text": "But you have never examined Aether's internal research logs from their Fremont facility, correct? So you cannot rule out that Aether independently arrived at a similar optimization through parallel research?", "phase": "Witness"},
            {"agent": "Witness",    "text": "I reviewed the logs that were disclosed. The 2021 logs describe a single-layer cathode — not the multi-layer architecture at issue. The NX-7's three-layer design was developed in mid-2022, after Aether's disclosed research ended.", "phase": "Witness"},

            # --- Redirect: Dr. Marsh ---
            {"agent": "Prosecutor", "text": "One question on redirect, Dr. Marsh. Does any published, open-access literature describe the exact combination of three thickness ratios and the nickel-aluminum dopant sequence found in both NX-7 and PowerCell's PC-900?", "phase": "Witness"},
            {"agent": "Witness",    "text": "No. I conducted a comprehensive literature review as part of this litigation. No journal article, patent, or conference proceeding describes this specific combination. It exists only in Nexus's internal records — and now in PowerCell's product.", "phase": "Witness"},
            {"agent": "Fact Checker", "text": "✓ Literature review documented in expert report. No prior art found.",                                                                                                            "phase": "Witness"},

            # --- Defense Witness: Dr. Raj Mehta ---
            {"agent": "Defense",    "text": "The defense calls Dr. Raj Mehta, independent materials scientist. Dr. Mehta — in your opinion, is cathode layering a proprietary technology or an industry-standard technique?",   "phase": "Witness"},
            {"agent": "Witness",    "text": "Cathode layering has been standard industry practice since at least 2009. The concept of stacking lithium cobalt oxide with manganese spinel interlayers is taught in graduate materials science programs. The specific thickness ratios will naturally converge when engineers optimize for the same performance targets — energy density, thermal stability, and cycle life.", "phase": "Witness"},
            {"agent": "Prosecutor", "text": "Dr. Mehta — you have never worked at Nexus Corp. or Aether Labs. You were retained by Aether's law firm three months ago for this litigation at a fee of $750 per hour. Your entire knowledge of this case comes from documents Aether selected to show you — correct?", "phase": "Witness"},
            {"agent": "Witness",    "text": "I was retained as a consultant, yes. My hourly rate is standard for an expert of my seniority. I reviewed the documents available to both parties through discovery.",                 "phase": "Witness"},
            {"agent": "Prosecutor", "text": "But you did not inspect the PowerCell PC-900 physical product yourself. Your opinion is based entirely on Aether's description of what was shared — correct?",                      "phase": "Witness"},
            {"agent": "Witness",    "text": "Correct. I did not physically examine the PowerCell product. My analysis is based on the disclosed specifications.",                                                                  "phase": "Witness"},
            {"agent": "Fact Checker", "text": "✓ Witness acknowledges limited scope of analysis. ✓ Financial interest disclosed.",                                                                                            "phase": "Witness"},

            # ════════════════ PHASE 6: REBUTTAL EVIDENCE ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to rebuttal evidence.",                                                                                                                                  "phase": "Rebuttal"},
            {"agent": "Judge",      "text": "Plaintiff — rebuttal?",                                                                                                                                                              "phase": "Rebuttal"},
            {"agent": "Prosecutor", "text": "Dr. Mehta testified that cathode layering is standard. But the defense has not produced a single example from the public domain matching the NX-7's specific three-layer architecture with its dopant sequence. If this technology is so standard — where is it? We submit that the defense's 'industry standard' argument fails because it cannot identify a single prior instance.", "phase": "Rebuttal"},
            {"agent": "Judge",      "text": "Defense — surrebuttal?",                                                                                                                                                             "phase": "Rebuttal"},
            {"agent": "Defense",    "text": "The plaintiff shifts the burden. We do not need to find an identical match in the public domain — we only need to show that the underlying technique is general knowledge. Cathode layering is general knowledge. The specific optimization path Nexus took toward the same goal is not protected by their NDA unless it explicitly covers specific thickness ratios — and their NDA does not.", "phase": "Rebuttal"},
            {"agent": "Fact Checker", "text": "✓ Parties disagree on interpretation. Underlying facts are not in dispute.",                                                                                                      "phase": "Rebuttal"},

            # ════════════════ PHASE 7: CLOSING ARGUMENTS ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to closing arguments.",                                                                                                                                "phase": "Closing"},
            {"agent": "Prosecutor", "text": "Ladies and gentlemen — think about what you have heard. A signed NDA that explicitly protects all technical specifications. An email from Aether's CTO attaching a file named after Nexus's internal project code. Dr. Marsh's unimpeached testimony — 94% structural match, with a combination so unique it exists nowhere in the published literature. Dr. Mehta, the defense's expert, never examined the PowerCell product. He was paid $750 an hour to review documents Aether selected for him. The NDA is clear. The email is damning. The science is conclusive. Aether Labs took Nexus's proprietary cathode technology and handed it to a competitor. By a preponderance of the evidence — you must find Aether Labs Liable for breach of contract.", "phase": "Closing"},
            {"agent": "Defense",    "text": "The plaintiff has built a castle on a filename. They cannot produce the file attached to that email. They cannot prove what was inside it. Dr. Marsh's 94% match — an impressive number — reflects an industry optimizing the same well-known parameters toward the same performance targets. Her probability calculation assumes independence between variables that she admitted are interdependent. And the NDA — read the text — protects 'technical specifications' shared between the parties. It does not protect generally known engineering techniques, which is exactly what cathode layering has been for fifteen years. A file name. A statistical calculation with a flawed assumption. A standard NDA that covers specifications, not science. The plaintiff has not proven breach by a preponderance of the evidence.", "phase": "Closing"},

            # ════════════════ PHASE 8: JURY INSTRUCTIONS ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to jury instructions.",                                                                                                                                "phase": "Jury Instructions"},
            {"agent": "Judge",      "text": "Members of the jury — this is a civil case for breach of contract. The plaintiff, Nexus Corporation, must prove its case by a preponderance of the evidence — meaning it is more likely than not that Aether Labs breached the NDA. To find Aether liable, you must find: (1) a valid NDA existed between the parties; (2) Aether disclosed protected information to a third party; (3) the disclosed information fell within the scope of the NDA's confidentiality clause; and (4) Nexus suffered damages as a result. Your verdict must be unanimous.", "phase": "Jury Instructions"},

            # ════════════════ PHASE 9: JURY DELIBERATION ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to jury deliberation.",                                                                                                                                "phase": "Jury Deliberation"},
            {"agent": "Foreperson", "text": "Initial positions, please.",                                                                                                                                                          "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #1 (Analytical): Liable. 94% match plus the email with Nexus's internal file name. Dr. Marsh was credible and thorough. The defense expert never examined the actual product.",   "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #2 (Skeptical): Liable. The file was literally named 'NX-Battery-Specs.' If Aether independently developed this, why use Nexus's naming convention? That shows knowledge of origin.", "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #3 (Empathetic): Liable. An NDA is an NDA. You sign it, you honor it. The email proves they shared something related to Nexus's specs.",                                           "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #4 (Pragmatic): Not Liable. The NDA wording is genuinely vague. 'Technical specifications' could mean anything. The defense raised enough doubt for me — this isn't criminal beyond reasonable doubt, but I'm not at 51% for the plaintiff.", "phase": "Jury Deliberation"},
            {"agent": "Foreperson", "text": "Round 1: 3 Liable, 1 Not Liable. Juror #4 — what would change your mind?",                                                                                                              "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #4: Actually — thinking about Dr. Marsh's testimony again. She said this specific combination exists nowhere in the published literature. That's a fact the defense didn't rebut. If Nexus alone had this unique combination, and now PowerCell has it, and Aether is the only link... I'm moving to Liable.", "phase": "Jury Deliberation"},
            {"agent": "Foreperson", "text": "Round 2: 4 Liable, 0 Not Liable. Unanimous verdict reached.",                                                                                                                          "phase": "Jury Deliberation"},

            # ════════════════ PHASE 10: SHADOW JURY ════════════════
            {"agent": "Bailiff",    "text": "The shadow jury has convened for analysis.",                                                                                                                                        "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 1: The email with 'NX-Battery-Specs-v3.pdf' combined with the 94% structural match — that's direct and circumstantial evidence aligning. Very strong for the plaintiff. [Vote: Liable, confidence 85%]", "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 2: The NDA is clear. Clause 3.1 covers 'all technical specifications.' Aether's email to PowerCell with a Nexus-labeled file is clear conduct. [Vote: Liable, confidence 78%]", "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 3: The fact that the specific combination exists nowhere in published literature is decisive. The defense never rebutted that. [Vote: Liable, confidence 72%]",             "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 4: Dr. Mehta seemed credible but his analysis was limited — he never saw the physical product. Dr. Marsh did. Physical inspection matters. [Vote: Liable, confidence 81%]", "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 5: The NDA could be clearer about scope. But Aether's conduct — naming a file after Nexus's internal designation — shows they themselves believed it was covered. [Vote: Liable, confidence 69%]", "phase": "Shadow Jury"},
            {"agent": "Bailiff",    "text": "The shadow jury has completed its analysis.",                                                                                                                                       "phase": "Shadow Jury"},

            # ════════════════ PHASE 11: VERDICT ════════════════
            {"agent": "Bailiff",    "text": "All rise for the reading of the verdict.",                                                                                                                                           "phase": "Verdict"},
            {"agent": "Judge",      "text": "The jury finds Aether Laboratories LIABLE for breach of the Non-Disclosure Agreement with Nexus Corporation. We will now proceed to the damages phase.",                               "phase": "Verdict"},

            # ════════════════ PHASE 12: SENTENCING / DAMAGES ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to the damages assessment.",                                                                                                                               "phase": "Sentencing"},
            {"agent": "Judge",      "text": "Having found Aether Labs liable, the court will now assess damages. Plaintiff's counsel — you may address the court.",                                                                "phase": "Sentencing"},
            {"agent": "Prosecutor", "text": "Your Honor, Nexus Corp. invested $18 million and four years developing the NX-7 cathode technology. The breach allowed PowerCell — a direct competitor — to bring a competing product to market in under nine months, bypassing R&D. Nexus lost a two-year exclusive market window valued at $3.2 million in projected revenue. Additionally, the loss of exclusivity depreciated Nexus's patent portfolio by an estimated $800,000. We request $4 million in compensatory damages plus legal costs.", "phase": "Sentencing"},
            {"agent": "Judge",      "text": "Defense counsel — you may address the court on mitigation.",                                                                                                                           "phase": "Sentencing"},
            {"agent": "Defense",    "text": "Your Honor, Aether Labs is a 45-employee research startup. A $4 million judgment would bankrupt the company and eliminate 45 jobs. The plaintiff's $3.2 million revenue projection assumes 100% market capture, which is unrealistic in the battery industry where multiple suppliers serve the same customers. Furthermore, the information shared was largely general engineering knowledge — the specific proprietary elements constitute at most 20% of what was communicated. We ask the court to assess damages at no more than $500,000, reflecting actual lost licensing value.", "phase": "Sentencing"},
            {"agent": "Judge",      "text": "The court has considered both submissions. Nexus Corporation — your development investment was substantial, and the breach deprived you of the exclusivity the NDA was designed to protect. Aether Labs — the court acknowledges your limited resources and the fact that not all information shared was proprietary. However, the email's deliberate use of Nexus's internal file designation shows knowing conduct. The court awards the following: Compensatory damages of $1.4 million, reflecting the lost licensing opportunity over the two-year exclusivity window, discounted for realistic market share. Legal costs of $300,000. Total judgment: $1,700,000. This court is adjourned.", "phase": "Sentencing"},

            # ════════════════ PHASE 13: COURT REPORTER ════════════════
            {"agent": "Bailiff",    "text": "Case 24-CV-0342 — Nexus Corporation versus Aether Laboratories — is concluded. The trial record shall be certified by the court reporter.",                                          "phase": "Court Reporter Log"},
            {"agent": "System",     "text": "[Court Reporter Log: Complete trial record compiled. Case 24-CV-0342. Verdict: LIABLE. Damages: $1.7 million. Transcript includes 3 exhibits, 2 witnesses including 1 expert qualification, 3 objections with rulings, 2 pre-trial motions, 4-phase adversarial process, 5 shadow juror analyses, full damages hearing.]", "phase": "Court Reporter Log"},

            # ════════════════ ADJOURNED ════════════════
            {"agent": "Bailiff",    "text": "All matters have been adjudicated. This court is adjourned.",                                                                                                                          "phase": "Adjourned"},
        ],
        "verdict": "LIABLE",
        "win_probability": 0.82,
        "sensitivity": "If the email had been excluded → Plaintiff win probability drops to 41%",
        "sentence": {
            "sentence": "The court finds Aether Labs liable for breach of the NDA and awards compensatory damages.",
            "term": "$1.4 million in compensatory damages, plus $300,000 in legal costs.",
            "rationale": "The 94% structural match combined with the email containing Nexus's internal file designation constitutes clear breach. Damages reflect lost licensing revenue and legal expenses."
        },
        "shadow_jury_narrative": [
            {"name": "Shadow Juror 1", "content": "The email with file name 'NX-Battery-Specs-v3.pdf' is damning. Combined with the 94% structural match, this is clear breach. [Vote: Liable]"},
            {"name": "Shadow Juror 2", "content": "The NDA explicitly covers 'all technical specifications.' Aether shared them with PowerCell. The intent is evident from the email. [Vote: Liable]"},
            {"name": "Shadow Juror 3", "content": "While cathode layering is known industry technique, the specific thickness ratios are proprietary. The match is too precise to be coincidence. [Vote: Liable]"},
            {"name": "Shadow Juror 4", "content": "The NDA wording could be clearer, but the email shows Aether knew the information was confidential. They proceeded anyway. [Vote: Liable]"},
            {"name": "Shadow Juror 5", "content": "Independent development is a weak defense when the file was literally named after Nexus's internal designation. [Vote: Liable]"},
        ],
    },

    "vance": {
        "title": "State v. Emilia Vance — Double Homicide by Arson",
        "jurisdiction": "United States · CA Central District",
        "description": (
            "The defendant, Emilia Vance, is charged with two counts of first-degree murder "
            "and one count of arson. On September 12th, a fire destroyed the Northside Storage "
            "warehouse, killing night security guards Richard Torres and Dana Kim. The prosecution "
            "alleges Vance, the warehouse's former manager, set the fire to destroy evidence of "
            "an ongoing $340,000 embezzlement scheme. Forensic fire investigator Dr. Marcus Chen "
            "identified an accelerant pour pattern at three separate origins, consistent with "
            "deliberate ignition using gasoline. Cell tower records from AT&T place Vance's phone "
            "near the warehouse at 11:30 PM — 10 minutes before the first 911 call. Security guard "
            "Paul Brennan reported seeing a woman matching Vance's description flee the east entrance "
            "at 11:35 PM. Brennan was fired by Vance six months prior for theft and has a prior "
            "conviction for perjury in 2019. A hardware store receipt dated September 10th shows "
            "a cash purchase of two 5-gallon gas cans signed 'E. Vance.' No fingerprints or DNA "
            "link Vance to the scene. Vance claims she was home watching television; her brother "
            "confirms she was there but admits he was asleep. Defense will call electrical engineer "
            "Dr. Priya Sharma to testify that faulty wiring could have caused the fire."
        ),
        "questions": [
            "Were accelerant residues tested for DNA or fingerprint evidence?",
            "How far is the defendant's home from the Northside Storage warehouse?",
            "Did the hardware store have surveillance footage matching the receipt date?",
            "Does the cell tower data distinguish between being inside versus near the building?",
            "Was the building's electrical system inspected before or after the fire?",
        ],
        "trial_script": [
            # ════════════════ PHASE 1: DISCOVERY ════════════════
            {"agent": "Bailiff",    "text": "All rise. The Honorable Justice Cross presiding. The court is now in session for the Discovery Disclosure phase.",                                                                            "phase": "Discovery"},
            {"agent": "Judge",      "text": "Be seated. We proceed with discovery disclosure in the matter of State versus Emilia Vance — two counts of first-degree murder and arson. Mr. Mercer, the People will disclose first.",         "phase": "Discovery"},
            {"agent": "Prosecutor", "text": "The People disclose the following: (1) Accelerant residue analysis by Dr. Marcus Chen; (2) AT&T cell tower records for device #310-555-0198; (3) Security guard Paul Brennan's written statement; (4) Hardware store receipt from September 10th; (5) Medical examiner autopsy reports for Torres and Kim.", "phase": "Discovery"},
            {"agent": "Defense",    "text": "The defense discloses: (1) Expert report by Dr. Priya Sharma on electrical anomalies in the southeast quadrant; (2) Sworn affidavit by James Vance confirming his sister's presence at home on the night in question.", "phase": "Discovery"},
            {"agent": "Judge",      "text": "Disclosure is complete. The court notes the defense has reserved the right to call additional witnesses. Proceed to pre-trial motions.",                                                            "phase": "Discovery"},

            # ════════════════ PHASE 2: PRE-TRIAL MOTIONS ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to pre-trial motions.",                                                                                                                                                  "phase": "Motions"},
            {"agent": "Judge",      "text": "Defense counsel, you filed a motion to suppress the cell tower records. State your grounds.",                                                                                                        "phase": "Motions"},
            {"agent": "Defense",    "text": "Your Honor, the prosecution's cell tower expert did not provide a written methodology. AT&T's standard records custodian cannot verify the GPS radius of the tower ping. Without verifiable methodology, the records lack proper foundation under FRE 702 and Daubert.", "phase": "Motions"},
            {"agent": "Prosecutor", "text": "The People respond: the records custodian will testify to the normal course of business record-keeping under FRE 803(6). Cell tower data is routinely admitted. The defense is conflating weight with admissibility.", "phase": "Motions"},
            {"agent": "Judge",      "text": "Motion to suppress cell tower records is DENIED. The records are business records under FRE 803(6). The radius margin goes to weight, not admissibility — the defense may cross-examine on it.",   "phase": "Motions"},
            {"agent": "Prosecutor", "text": "The People move under FRE 609(a)(1) to admit guard Paul Brennan's 2019 perjury conviction for impeachment purposes. The defense concedes the credibility of Brennan is material.",                 "phase": "Motions"},
            {"agent": "Defense",    "text": "Yes, Your Honor. The defense acknowledges Brennan's credibility is relevant and does not oppose admission. However, we request that the prior firing — which shows Brennan's bias against the defendant — also be admitted.", "phase": "Motions"},
            {"agent": "Judge",      "text": "Motion GRANTED in part. Brennan's 2019 perjury conviction is admitted for impeachment purposes under FRE 609. Evidence of his termination by the defendant is also admissible to show bias. Both sides may explore these on cross-examination.", "phase": "Motions"},

            # ════════════════ PHASE 3: OPENING STATEMENTS ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to opening statements.",                                                                                                                                                 "phase": "Opening"},
            {"agent": "Judge",      "text": "Mr. Mercer — the People's opening statement, please.",                                                                                                                                              "phase": "Opening"},
            {"agent": "Prosecutor", "text": "Ladies and gentlemen of the jury: on September 12th, two security guards — Richard Torres and Dana Kim — went to work at Northside Storage warehouse. They never came home. The evidence will show that Emilia Vance, the warehouse's former manager, doused that building in gasoline and ignited it to conceal $340,000 in embezzled funds. A forensic fire investigator traced the fire to three separate accelerant pour points. Cell tower records place the defendant's phone at the warehouse ten minutes before the blaze. A receipt signed 'E. Vance' documents the purchase of gas cans two days earlier. And at 11:35 PM, a guard saw a woman matching Vance's description running from the east entrance. Two lives were taken. The evidence points to one conclusion.", "phase": "Opening"},
            {"agent": "Judge",      "text": "Defense counsel.",                                                                                                                                                                                  "phase": "Opening"},
            {"agent": "Defense",    "text": "Members of the jury — the prosecution wants you to convict on a tower ping, a receipt, and a shadowy silhouette. But here is what they do not have: no fingerprints at the scene. No DNA on any container. No surveillance footage showing my client anywhere near that warehouse. No eyewitness who can identify her face. Their star witness — Paul Brennan — was fired by Ms. Vance for stealing from this very warehouse, and he was convicted of lying under oath. The fire investigator never examined the actual wiring, which our electrical engineer will show was corroded and unsafe. Emilia Vance is innocent. The state has not met its burden.", "phase": "Opening"},

            # ════════════════ PHASE 4: EVIDENCE PRESENTATION ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to evidence presentation.",                                                                                                                                              "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "The People submit Exhibit A: the accelerant residue analysis report by Dr. Marcus Chen, documenting gasoline residues at three separate origin points in the southeast quadrant.",                     "phase": "Evidence"},
            {"agent": "Defense",    "text": "Objection — lack of foundation, Your Honor. Dr. Chen has not yet been qualified as an expert in fire forensics. His credentials must be established before his report can be admitted.",               "phase": "Evidence"},
            {"agent": "Judge",      "text": "Sustained. Exhibit A is conditionally admitted pending expert qualification of Dr. Chen during witness examination. FRE 702. The report will be admitted subject to voir dire.",                       "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "The People submit Exhibit B: the hardware store receipt dated September 10th at 4:15 PM — two 5-gallon gas cans, cash purchase, signed 'E. Vance.'",                                                 "phase": "Evidence"},
            {"agent": "Defense",    "text": "Objection — hearsay. The receipt is an out-of-court statement offered for the truth of the matter asserted: that Emilia Vance purchased gas cans. It is testimonial hearsay.",                         "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "The receipt is a business record, Your Honor. The hardware store's manager will testify that the receipt was generated in the regular course of business at or near the time of the transaction, and that it is the store's regular practice to record such sales. FRE 803(6) — the business records exception.", "phase": "Evidence"},
            {"agent": "Judge",      "text": "Overruled. The receipt qualifies as a business record under FRE 803(6) — made at or near the time by a person with knowledge, kept in the regular course of business, and the store's regular practice. Weight is a matter for the jury.", "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "The People submit Exhibit C: crime scene photographs, including images of the victims' remains as they were found by firefighters.",                                                                 "phase": "Evidence"},
            {"agent": "Defense",    "text": "Objection — FRE 403. The probative value of these photographs is substantially outweighed by the danger of unfair prejudice. They will inflame the jury's emotions without adding any fact in dispute.", "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "The photos show the location of the victims relative to the three origin points Dr. Chen identified. They are necessary to establish that both victims were trapped by the same three fires.",        "phase": "Evidence"},
            {"agent": "Judge",      "text": "Overruled. The People have established probative value — the photos demonstrate the spatial relationship between the fire origins and the victims. The court finds their probative value not substantially outweighed by prejudice. FRE 403.", "phase": "Evidence"},
            {"agent": "Defense",    "text": "The defense submits Exhibit D: Dr. Priya Sharma's electrical inspection report, documenting corroded wiring in the southeast quadrant consistent with an electrical fire origin.",                    "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "No objection, Your Honor. We welcome the defense's alternate theory.",                                                                                                                              "phase": "Evidence"},
            {"agent": "Judge",      "text": "Exhibit D admitted without objection.",                                                                                                                                                             "phase": "Evidence"},

            # ════════════════ PHASE 5: WITNESS EXAMINATION ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to witness examination.",                                                                                                                                               "phase": "Witness"},

            # --- Expert Witness: Dr. Marcus Chen ---
            {"agent": "Prosecutor", "text": "The People call Dr. Marcus Chen, Chief Fire Investigator for the California State Fire Marshal's Office. Dr. Chen — please state your qualifications for the court.",                                "phase": "Witness"},
            {"agent": "Witness",    "text": "I hold a Ph.D. in Combustion Chemistry from Stanford University. I have 22 years of experience in fire investigation, have testified as an expert in 47 trials, and have authored 18 peer-reviewed papers on accelerant detection methodology. I am certified by the National Association of Fire Investigators.", "phase": "Witness"},
            {"agent": "Judge",      "text": "Dr. Chen — are your methodologies generally accepted in the scientific community?",                                                                                                                "phase": "Witness"},
            {"agent": "Witness",    "text": "Yes, Your Honor. Gas chromatography-mass spectrometry is the gold standard for accelerant residue analysis. It is accepted internationally and has been validated in hundreds of studies.",         "phase": "Witness"},
            {"agent": "Judge",      "text": "Defense counsel, would you like to voir dire the witness on his qualifications?",                                                                                                                   "phase": "Witness"},
            {"agent": "Defense",    "text": "Dr. Chen — have you ever conducted a field test under conditions that also included electrical fire ignition? And has your accelerant detection methodology ever been successfully challenged in a Daubert hearing?", "phase": "Witness"},
            {"agent": "Witness",    "text": "Yes to the first — I have investigated fires with multiple potential causes. To the second — my methodology was subjected to a Daubert challenge in the 2017 Arroyo County case and was upheld by the court of appeals.", "phase": "Witness"},
            {"agent": "Defense",    "text": "No further questions on qualifications, Your Honor.",                                                                                                                                               "phase": "Witness"},
            {"agent": "Judge",      "text": "The court finds Dr. Chen qualified as an expert in fire forensics under FRE 702. Exhibit A — the accelerant report — is formally admitted. Dr. Chen, you may testify.",                              "phase": "Witness"},

            # --- Direct: Dr. Chen ---
            {"agent": "Prosecutor", "text": "Dr. Chen — describe your findings at Northside Storage warehouse.",                                                                                                                                  "phase": "Witness"},
            {"agent": "Witness",    "text": "I identified the presence of gasoline residues — a medium petroleum distillate — at three physically distinct locations in the southeast quadrant. The pour pattern indicates deliberate human placement. The fires were not connected by electrical pathways or shared fuel sources — three independent ignitions.", "phase": "Witness"},
            {"agent": "Prosecutor", "text": "Could faulty electrical wiring have caused this pattern?",                                                                                                                                            "phase": "Witness"},
            {"agent": "Witness",    "text": "No. Electrical fires start at a single point and follow wiring conduits. A three-point, simultaneous ignition with accelerant residues is inconsistent with any natural or electrical cause. I examined the wiring at all three locations — it was intact.", "phase": "Witness"},
            {"agent": "Fact Checker", "text": "✓ Testimony consistent with report. No discrepancies detected.",                                                                                                                                    "phase": "Witness"},

            # --- Cross: Dr. Chen (defense attacks methodology) ---
            {"agent": "Defense",    "text": "Dr. Chen — you stated the wiring at the three origin points was intact. Did you personally examine the wiring in the building's eastern corridor — that is, the wiring that Dr. Sharma later identified as corroded?", "phase": "Witness"},
            {"agent": "Witness",    "text": "I examined the wiring within an 8-foot radius of each origin point, which is standard NFPA 921 protocol. The eastern corridor is approximately 40 feet from the nearest origin. I did not examine that corridor's wiring.", "phase": "Witness"},
            {"agent": "Defense",    "text": "So it is possible — scientifically — that a fire started in the eastern corridor from faulty wiring, and then separately ignited gasoline residue stored in the southeast quadrant?",                 "phase": "Witness"},
            {"agent": "Witness",    "text": "Theoretically, a fire could travel 40 feet along wooden shelving. But my analysis shows the southeast quadrant was the origin based on deepest char patterns. The eastern corridor showed secondary burn damage — meaning the fire reached it later.", "phase": "Witness"},

            # --- Redirect: Dr. Chen ---
            {"agent": "Prosecutor", "text": "Dr. Chen — one question on redirect. In your 22 years and 47 trials, has NFPA 921's standard 8-foot radius examination protocol EVER failed to correctly identify the fire's origin point?",       "phase": "Witness"},
            {"agent": "Witness",    "text": "No. The NFPA 921 protocol has been validated across thousands of investigations. I have never encountered a case where the correct origin was more than the standard protocol distance from the deepest char.", "phase": "Witness"},
            {"agent": "Fact Checker", "text": "✓ Statement verified. NFPA 921 is the industry standard.",                                                                                                                                          "phase": "Witness"},

            # --- Eyewitness: Paul Brennan (with impeachment hook) ---
            {"agent": "Prosecutor", "text": "The People call Paul Brennan. Mr. Brennan — you were working as a security guard at Northside Storage on September 12th. Describe what you saw at 11:35 PM.",                                          "phase": "Witness"},
            {"agent": "Witness",    "text": "I was making my rounds near the east entrance. I saw a woman running from the building — dark coat, shoulder-length brown hair, about five-foot-six. She got into a silver sedan and drove off. Maybe 90 seconds later I smelled smoke. I called 911.", "phase": "Witness"},
            {"agent": "Prosecutor", "text": "Was the area well-lit?",                                                                                                                                                                               "phase": "Witness"},
            {"agent": "Witness",    "text": "There are floodlights above the east entrance. Yes — well-lit. I could see her clearly.",                                                                                                              "phase": "Witness"},

            # --- Cross: Brennan (impeachment — bias + character) ---
            {"agent": "Defense",    "text": "Mr. Brennan — you were fired by Emilia Vance from this very warehouse six months before the fire, correct?",                                                                                          "phase": "Witness"},
            {"agent": "Witness",    "text": "I... yes. She terminated my employment.",                                                                                                                                                              "phase": "Witness"},
            {"agent": "Defense",    "text": "The termination letter states you were fired for theft of warehouse inventory — $8,200 worth of copper fittings. Is that correct?",                                                                    "phase": "Witness"},
            {"agent": "Witness",    "text": "That's what the letter says. I maintain I was wrongly accused.",                                                                                                                                       "phase": "Witness"},
            {"agent": "Defense",    "text": "And in 2019 — you were convicted of perjury for lying under oath in a civil deposition about a former employer. You served six months, did you not?",                                                  "phase": "Witness"},
            {"agent": "Witness",    "text": "Yes... that was a misunderstanding. But yes, I was convicted.",                                                                                                                                        "phase": "Witness"},
            {"agent": "Defense",    "text": "No further questions, Your Honor. The jury can assess Mr. Brennan's credibility.",                                                                                                                     "phase": "Witness"},

            # --- Redirect: Brennan ---
            {"agent": "Prosecutor", "text": "Mr. Brennan — has your testimony today about what you saw at 11:35 PM on September 12th ever changed from your initial 911 call or your deposition?",                                                 "phase": "Witness"},
            {"agent": "Witness",    "text": "No. It has been consistent from the night of the fire. I have never wavered on what I saw.",                                                                                                           "phase": "Witness"},
            {"agent": "Fact Checker", "text": "✓ Direct testimony is consistent with 911 call transcript.",                                                                                                                                         "phase": "Witness"},

            # --- Investigative Witness: Detective Reyes ---
            {"agent": "Prosecutor", "text": "The People call Detective Paula Reyes of the Arson Investigation Unit. Detective — describe the cell tower data linking Vance to the scene.",                                                         "phase": "Witness"},
            {"agent": "Witness",    "text": "AT&T records show device number 310-555-0198 — registered to Emilia Vance — connected to tower 847 at 11:27 PM and disconnected at 11:34 PM. That tower covers a sector radius of approximately 1,200 feet that includes the warehouse. Her phone did not connect to any tower near her home address between those times.", "phase": "Witness"},
            {"agent": "Fact Checker", "text": "✓ Records corroborated. Tower 847 coverage map verified.",                                                                                                                                           "phase": "Witness"},

            {"agent": "Defense",    "text": "Detective — the 1,200-foot radius you mentioned covers the warehouse. Does it also cover the adjacent industrial park, the truck stop, and the twenty-four-hour gym across the street?",               "phase": "Witness"},
            {"agent": "Witness",    "text": "Yes. The sector covers all those locations.",                                                                                                                                                          "phase": "Witness"},
            {"agent": "Defense",    "text": "So her phone being in that 1,200-foot radius does not prove she was INSIDE the warehouse.",                                                                                                            "phase": "Witness"},
            {"agent": "Witness",    "text": "That is correct. The data places the phone in the coverage area — not inside the building.",                                                                                                            "phase": "Witness"},

            # --- Defendant: Emilia Vance ---
            {"agent": "Defense",    "text": "The defense calls Emilia Vance. Ms. Vance — where were you on the night of September 12th at 11:30 PM?",                                                                                              "phase": "Witness"},
            {"agent": "Witness",    "text": "I was at home watching television. I lived with my brother James at 1842 Oakdale Drive. I never left the house that night.",                                                                           "phase": "Witness"},
            {"agent": "Defense",    "text": "Why was your phone near the warehouse?",                                                                                                                                                              "phase": "Witness"},
            {"agent": "Witness",    "text": "I can't explain that. The phone was in my possession at home. I've asked AT&T to audit the tower data — maybe it logged the wrong tower.",                                                             "phase": "Witness"},

            {"agent": "Prosecutor", "text": "Ms. Vance — the hardware store receipt bears your signature. Two 5-gallon gas cans, purchased two days before the fire. For what purpose?",                                                           "phase": "Witness"},
            {"agent": "Witness",    "text": "That's not my signature. 'E. Vance' — that could be anyone. My married name is Vance. My maiden name was Ellis. I never sign as E. Vance.",                                                           "phase": "Witness"},
            {"agent": "Prosecutor", "text": "The receipt clerk described the buyer — dark coat, brown hair, five-foot-six. Is there another woman matching that description who would use the initials E. Vance?",                                  "phase": "Witness"},
            {"agent": "Witness",    "text": "Object — my counsel... I don't know who that was. But it wasn't me.",                                                                                                                                 "phase": "Witness"},
            {"agent": "Fact Checker", "text": "✓ No evidence linking specific clerk to specific transaction.",                                                                                                                                     "phase": "Witness"},

            # --- Character Witness: James Vance ---
            {"agent": "Defense",    "text": "The defense calls James Vance. Mr. Vance — you live with your sister at 1842 Oakdale Drive. Was she home the night of September 12th?",                                                               "phase": "Witness"},
            {"agent": "Witness",    "text": "Yes. I saw her in the living room around 9 PM. When I went to bed at ten, her car was still in the driveway. In the morning, it was still there. She was home all night.",                            "phase": "Witness"},
            {"agent": "Prosecutor", "text": "Mr. Vance — you testified you were asleep from 10 PM to 7 AM. You cannot confirm your sister was home at 11:30 PM, can you?",                                                                        "phase": "Witness"},
            {"agent": "Witness",    "text": "No... I was asleep. But her car was there in the morning.",                                                                                                                                           "phase": "Witness"},
            {"agent": "Prosecutor", "text": "And she had a second key to your car — your silver sedan. Is that correct?",                                                                                                                          "phase": "Witness"},
            {"agent": "Witness",    "text": "...Yes.",                                                                                                                                                                                             "phase": "Witness"},
            {"agent": "Fact Checker", "text": "✓ Vehicle registration confirms James Vance owns a silver sedan.",                                                                                                                                   "phase": "Witness"},

            # ════════════════ PHASE 6: REBUTTAL EVIDENCE ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to rebuttal evidence.",                                                                                                                                                    "phase": "Rebuttal"},
            {"agent": "Judge",      "text": "Mr. Mercer — the prosecution may present rebuttal evidence.",                                                                                                                                          "phase": "Rebuttal"},
            {"agent": "Prosecutor", "text": "The People recall Dr. Chen in rebuttal. Dr. Chen — the defense has introduced Exhibit D suggesting electrical wiring was corroded. Does corroded wiring cause three simultaneous gasoline fires at separate locations?", "phase": "Rebuttal"},
            {"agent": "Witness",    "text": "No. Even if wiring were severely corroded, the maximum temperature of an electrical arc is insufficient to ignite gasoline at a distance. Gasoline requires direct flame or spark contact. Three independent fires at separated locations, each with accelerant residue — that is human ignition.", "phase": "Rebuttal"},
            {"agent": "Judge",      "text": "Defense counsel — surrebuttal?",                                                                                                                                                                       "phase": "Rebuttal"},
            {"agent": "Defense",    "text": "Dr. Chen — you have not examined the wire samples that Dr. Sharma analyzed. So your opinion on the eastern corridor wiring is theoretical — not based on direct observation of that specific wiring, correct?", "phase": "Rebuttal"},
            {"agent": "Witness",    "text": "I did not examine those specific wire samples, correct. My analysis is based on NFPA 921 methodology applied to the origin points I did examine.",                                                     "phase": "Rebuttal"},
            {"agent": "Fact Checker", "text": "✓ Both parties' expert testimony noted. Jury may weigh competing opinions.",                                                                                                                         "phase": "Rebuttal"},

            # ════════════════ PHASE 7: CLOSING ARGUMENTS ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to closing arguments.",                                                                                                                                                    "phase": "Closing"},
            {"agent": "Prosecutor", "text": "Members of the jury — consider what you have heard. An expert with 22 years of experience found three separate gasoline fires, each set deliberately. Cell tower records put the defendant's phone at the warehouse ten minutes before the blaze. A receipt, signed in a name matching the defendant, documents the purchase of gas cans two days before. A guard saw a woman matching the defendant's description fleeing. The defendant had motive — $340,000 in embezzled money and a fire that conveniently destroyed the paper trail. That is not coincidence. That is murder in the first degree. The People ask you to return a verdict of Guilty on all counts.", "phase": "Closing"},
            {"agent": "Defense",    "text": "The prosecution has asked you to convict on suspicion. Let me remind you what the standard is: proof beyond a reasonable doubt. Not 'probably' — not 'likely' — beyond reasonable doubt. Where are the fingerprints? Where is the DNA? Where is the video? Their eyewitness is a convicted perjurer who was fired by my client for theft. Their cell tower data covers 1,200 feet — a truck stop, a gym, an industrial park. Their receipt was signed by 'E. Vance' — with no handwriting analysis. And their fire expert never examined the corroded wiring that our engineer says could have started the fire. Every piece of evidence has a gap. Gaps add up to reasonable doubt. You must find Emilia Vance Not Guilty.", "phase": "Closing"},

            # ════════════════ PHASE 8: JURY INSTRUCTIONS ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to jury instructions.",                                                                                                                                                    "phase": "Jury Instructions"},
            {"agent": "Judge",      "text": "Ladies and gentlemen of the jury — I will now instruct you on the law that governs this case. Count One and Count Two charge the defendant with First-Degree Murder under California Penal Code 187(a). To find the defendant guilty, you must find that the prosecution has proven beyond a reasonable doubt: (1) the defendant committed an act that caused the death of another person, (2) the act was done with malice aforethought, and (3) the killing was willful, deliberate, and premeditated. Count Three charges Arson under Penal Code 451(b) — the willful and malicious burning of a structure. Your verdict must be unanimous. You must not be influenced by pity or prejudice. Consider all the evidence fairly.", "phase": "Jury Instructions"},

            # ════════════════ PHASE 9: JURY DELIBERATION ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to jury deliberation.",                                                                                                                                                    "phase": "Jury Deliberation"},
            {"agent": "Foreperson", "text": "Let us begin deliberations. Please state your initial positions on the murder counts.",                                                                                                               "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #1 (Analytical): Guilty. The cell tower data plus the receipt plus the eyewitness — three independent lines of evidence all point to the same conclusion at the same time.",                       "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #2 (Skeptical): Not Guilty. The eyewitness has a perjury conviction. That alone creates reasonable doubt for me. And the cell tower doesn't prove she was inside.",                               "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #3 (Empathetic): Guilty. The expert testimony was clear. Three separate fires with accelerant. The wiring theory doesn't explain that. Someone set those fires.",                                 "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #4 (Pragmatic): Undecided. The evidence is circumstantial but it's a lot of circumstances aligning.",                                                                                             "phase": "Jury Deliberation"},
            {"agent": "Foreperson", "text": "Round 1: 2 Guilty, 1 Not Guilty, 1 Undecided. Juror #2 — what would it take for you to reconsider?",                                                                                                  "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #2: If the receipt were matched by handwriting analysis, I would be there. But the prosecution didn't do that. However... three separate fires. The expert is convincing on the arson count. I could find Guilty on Arson but still have doubt on Murder.", "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #4: The expert said it was human ignition. If we accept arson — and the defendant's phone was there, she had motive, the receipt... I'm moving to Guilty on all counts.",                         "phase": "Jury Deliberation"},
            {"agent": "Foreperson", "text": "Round 2: 3 Guilty, 1 Not Guilty. Juror #2 — further thoughts?",                                                                                                                                      "phase": "Jury Deliberation"},
            {"agent": "Juror",      "text": "Juror #2: I have struggled with Brennan's credibility. But I separate him from the physical evidence. The three fires — that's not a coincidence. The receipt. The phone. I change my vote to Guilty on all counts.", "phase": "Jury Deliberation"},
            {"agent": "Foreperson", "text": "Round 3: 4 Guilty, 0 Not Guilty. Unanimous verdict reached on all three counts.",                                                                                                                     "phase": "Jury Deliberation"},

            # ════════════════ PHASE 10: SHADOW JURY ════════════════
            {"agent": "Bailiff",    "text": "The shadow jury has convened for analysis.",                                                                                                                                                          "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 1 (Liam): Accelerant expert testimony is compelling. Three separate fires by human ignition. Cell data places her at the scene. Receipt ties her to the materials. Prosecution's case is strong. [Vote: Guilty, confidence 82%]", "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 2 (Sarah): Brennan's bias and perjury conviction damage the eyewitness portion. But the physical evidence stands independently. The expert was thorough. [Vote: Guilty, confidence 73%]", "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 3 (Marcus): Circumstantial — but the receipt is a paper trail you can't ignore. Gas cans purchased, then three gas fires. That's direct enough for me. [Vote: Guilty, confidence 78%]", "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 4 (Elena): The defense's wiring theory has a problem — Dr. Sharma never inspected the scene. Dr. Chen did. Physical presence at the site matters. [Vote: Guilty, confidence 71%]",     "phase": "Shadow Jury"},
            {"agent": "Juror",      "text": "Shadow Juror 5 (David): If the defendant really embezzled the $340,000, that's a powerful motive. Were bank records examined? Without that, I see circumstantial — but still enough. [Vote: Guilty, confidence 68%]", "phase": "Shadow Jury"},
            {"agent": "Bailiff",    "text": "The shadow jury has completed its analysis.",                                                                                                                                                         "phase": "Shadow Jury"},

            # ════════════════ PHASE 11: SENTENCING ════════════════
            {"agent": "Bailiff",    "text": "The court will now proceed to sentencing.",                                                                                                                                                           "phase": "Sentencing"},
            {"agent": "Judge",      "text": "The jury has returned a verdict of Guilty on all counts. We now proceed to the sentencing phase. Mr. Mercer — the People may address the court on aggravation.",                                       "phase": "Sentencing"},
            {"agent": "Prosecutor", "text": "Your Honor, the People urge the maximum sentence. The defendant did not commit a crime of impulse — she planned this over days. She purchased gasoline containers. She waited for night shift. She poured accelerant at three locations to ensure maximum destruction. Two innocent people — Richard Torres, a father of three, and Dana Kim, a grandmother — were burned alive. Their smoke inhalation deaths mean they were conscious, coughing, suffocating, knowing they would die. The defendant set out to destroy evidence of embezzlement and did not care who she killed in the process. This is first-degree murder with malice aforethought, committed with premeditation and extreme cruelty. We request the court impose a sentence of life without the possibility of parole.", "phase": "Sentencing"},
            {"agent": "Judge",      "text": "Defense counsel — mitigation?",                                                                                                                                                                       "phase": "Sentencing"},
            {"agent": "Defense",    "text": "Your Honor, Emilia Vance is 38 years old. She has no prior criminal record. She volunteered at a youth shelter for six years. She has a twelve-year-old daughter. The court should consider that this case was built entirely on circumstantial evidence — there is nothing direct tying her to this crime. A life sentence means her daughter grows up without a mother. We ask the court to impose the minimum sentence and to consider that the embezzlement allegation — the state's own theory of motive — was never charged or proven. The state is asking you to sentence her for an unproven crime.", "phase": "Sentencing"},
            {"agent": "Judge",      "text": "The court has considered both aggravation and mitigation. Emilia Vance — please rise. The evidence at trial established beyond reasonable doubt that you set three separate fires in an occupied building, knowing two people were inside. You did so to destroy evidence of financial crimes. Richard Torres and Dana Kim died terrified, unable to escape a fire you set. Their families will carry that loss forever. However, this court also considers your lack of prior criminal history, your record of community service, and the needs of your daughter. The court hereby sentences you as follows: On Counts One and Two — First-Degree Murder — 25 years to life for each count, to be served concurrently. On Count Three — Arson — 8 years, concurrent. You are remanded to the custody of the California Department of Corrections. This court is adjourned.", "phase": "Sentencing"},

            # ════════════════ PHASE 12: COURT REPORTER ════════════════
            {"agent": "Bailiff",    "text": "Case 24-CF-0192 — State of California versus Emilia Vance — is concluded. The trial record shall be certified by the court reporter.",                                                                 "phase": "Court Reporter Log"},
            {"agent": "System",     "text": "[Court Reporter Log: Complete trial record compiled. Case 24-CF-0192. Verdict: Guilty on all counts. Sentence: 25 years to life, concurrent. Transcript includes 7 exhibits, 6 witnesses, 4 objections with rulings, 1 expert qualification, 2 impeachment challenges, 1 hearsay exception analysis, 3-round jury deliberation, 5 shadow juror analyses, and full sentencing hearing.]", "phase": "Court Reporter Log"},

            # ════════════════ ADJOURNED ════════════════
            {"agent": "Bailiff",    "text": "All charges have been adjudicated. This court is adjourned.",                                                                                                                                         "phase": "Adjourned"},
        ],
        "verdict": "GUILTY",
        "win_probability": 0.74,
        "sensitivity": "If Brennan's testimony is excluded → prosecution win probability drops to 51%",
        "sentence": {
            "sentence": "On Counts One and Two — First-Degree Murder — 25 years to life for each count, to be served concurrently. On Count Three — Arson — 8 years, concurrent.",
            "term": "25 years to life, concurrent on all counts. Parole eligibility after 25 years.",
            "rationale": "Aggravating factors: two victims, premeditation over multiple days, deliberate cruelty (smoke inhalation deaths while victims were conscious), arson used to conceal embezzlement. Mitigating factors: no prior criminal record, six years of community service at youth shelters, a 12-year-old dependent child."
        },
        "shadow_jury_narrative": [
            {"name": "Shadow Juror 1", "content": "Accelerant expert testimony is compelling. Three separate fires by human ignition. Cell data places her at the scene. Receipt ties her to the materials. Prosecution's case is strong. [Vote: Guilty, confidence 82%]"},
            {"name": "Shadow Juror 2", "content": "Brennan's bias and perjury conviction damage the eyewitness portion. But the physical evidence stands independently. The expert was thorough. [Vote: Guilty, confidence 73%]"},
            {"name": "Shadow Juror 3", "content": "Circumstantial — but the receipt is a paper trail you can't ignore. Gas cans purchased, then three gas fires. That's direct enough for me. [Vote: Guilty, confidence 78%]"},
            {"name": "Shadow Juror 4", "content": "The defense's wiring theory has a problem — Dr. Sharma never inspected the scene. Dr. Chen did. Physical presence at the site matters. [Vote: Guilty, confidence 71%]"},
            {"name": "Shadow Juror 5", "content": "If the defendant really embezzled the $340,000, that's a powerful motive. Were bank records examined? Without that, I see circumstantial — but still enough. [Vote: Guilty, confidence 68%]"},
        ],
    },
}
