"""
legalis/data.py
───────────────
Static demo-case data and agent styling constants.
Pulled out of app.py so the server layer stays thin.
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
            # ── Dramatic Opening ──
            {"agent": "Bailiff",    "text": "All rise. The Honorable Justice Vance presiding.",                                                                                                                                                 "phase": "Opening"},
            {"agent": "Judge",      "text": "You may be seated. This court is now in session — State versus Marcus Webb, charge of Grand Theft Auto in the First Degree. Are the prosecution and defense ready to proceed with opening statements?", "phase": "Opening"},
            {"agent": "Prosecutor", "text": "Ready, Your Honor.",                                                                                                                                                                               "phase": "Opening"},
            {"agent": "Defense",    "text": "The defense is ready, Your Honor.",                                                                                                                                                                "phase": "Opening"},
            {"agent": "Judge",      "text": "Proceed, Mr. Mercer.",                                                                                                                                                                             "phase": "Opening"},
            # ── Opening Arguments ──
            {"agent": "Prosecutor", "text": "Ladies and gentlemen — the evidence will show that at precisely 11:47 PM, March 14th, Marcus Webb stole a Tesla Model Y. Security footage places him at the scene. His alibi is a bartender who couldn't track his movements in a packed bar.", "phase": "Opening"},
            {"agent": "Defense",    "text": "The prosecution asks you to convict on a grainy silhouette. No fingerprints. No DNA. No recovered property. Reasonable doubt exists at every turn.",                                                                                                  "phase": "Opening"},
            # ── Evidence ──
            {"agent": "System",     "text": "— Evidence Presentation —",                                                                                                                                                              "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "The People submit Exhibit A: parking-lot camera footage, timestamped 11:47 PM, March 14th.",                                                                                             "phase": "Evidence"},
            {"agent": "Judge",      "text": "Exhibit A admitted into evidence.",                                                                                                                                                      "phase": "Evidence"},
            {"agent": "Defense",    "text": "Objection. The footage is 480p and the figure's face is not identifiable. Prejudicial without probative value.",                                                                        "phase": "Evidence"},
            {"agent": "Judge",      "text": "Overruled. Weight is for the jury. Exhibit A remains admitted. FRE 401.",                                                                                                                "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "The People submit Exhibit B: owner statement confirming the vehicle was locked and parked at 9:00 PM.",                                                                                  "phase": "Evidence"},
            {"agent": "Judge",      "text": "Exhibit B admitted.",                                                                                                                                                                    "phase": "Evidence"},
            # ── Witness ──
            {"agent": "System",     "text": "— Witness Examination —",                                                                                                                                                               "phase": "Witness"},
            {"agent": "Prosecutor", "text": "The People call Officer Daniels. Officer, describe what you observed at the scene.",                                                                                                     "phase": "Witness"},
            {"agent": "Witness",    "text": "I arrived at 12:15 AM. The spot was empty. I reviewed footage on-site — a figure matching Webb's height and build was near the vehicle at 11:47 PM.",                                   "phase": "Witness"},
            {"agent": "Defense",    "text": "Officer, you cannot identify the face in the footage — correct?",                                                                                                                        "phase": "Witness"},
            {"agent": "Witness",    "text": "Correct. The face is not clearly visible.",                                                                                                                                              "phase": "Witness"},
            {"agent": "Fact Checker", "text": "✓ Response verified against deposition. No inconsistencies detected.",                                                                                                                "phase": "Witness"},
            {"agent": "Defense",    "text": "The defense calls Sarah Lin. Ms. Lin, was Marcus Webb in the bar at 11:47 PM?",                                                                                                          "phase": "Witness"},
            {"agent": "Witness",    "text": "Yes. I served him around 11:30 and he was still there when I checked near midnight.",                                                                                                   "phase": "Witness"},
            {"agent": "Prosecutor", "text": "Ms. Lin, it was a busy Friday night. Could you have lost sight of him for 10–15 minutes?",                                                                                              "phase": "Witness"},
            {"agent": "Witness",    "text": "It was busy, yes. I... I don't recall a specific gap. But he was definitely there around that time.",                                                                                   "phase": "Witness"},
            # ── Closing ──
            {"agent": "System",     "text": "— Closing Arguments —",                                                                                                                                                                 "phase": "Closing"},
            {"agent": "Prosecutor", "text": "Camera places someone at the scene. The alibi witness admits gaps. The evidence points to one conclusion.",                                                                              "phase": "Closing"},
            {"agent": "Defense",    "text": "A shadow is not proof. No fingerprints. No DNA. No property recovered. The prosecution has not met its burden.",                                                                         "phase": "Closing"},
            # ── Deliberation ──
            {"agent": "System",     "text": "— Jury Deliberation —",                                                                                                                                                                 "phase": "Deliberation"},
            {"agent": "Judge",      "text": "Members of the jury — determine whether guilt has been proven beyond reasonable doubt. You must reach a unanimous verdict.",                                                             "phase": "Deliberation"},
            {"agent": "Foreperson", "text": "Each juror, please state your initial position.",                                                                                                                                        "phase": "Deliberation"},
            {"agent": "Juror",      "text": "Juror #1 (Analytical): Not Guilty. The footage is inconclusive. No forensic evidence.",                                                                                                 "phase": "Deliberation"},
            {"agent": "Juror",      "text": "Juror #2 (Empathetic): Not Guilty. I believe the bartender's testimony.",                                                                                                               "phase": "Deliberation"},
            {"agent": "Juror",      "text": "Juror #3 (Skeptical): Guilty. The bar was busy — she could have lost track. The camera puts someone his size right there.",                                                             "phase": "Deliberation"},
            {"agent": "Juror",      "text": "Juror #4 (Pragmatic): Not Guilty. Too many gaps. No physical evidence.",                                                                                                                "phase": "Deliberation"},
            {"agent": "Foreperson", "text": "Round 1: 3 Not Guilty, 1 Guilty. Juror #3 — please elaborate.",                                                                                                                        "phase": "Deliberation"},
            {"agent": "Juror",      "text": "Juror #3: Circumstantial is still evidence. But... without fingerprints or recovery, it's thin. I'll change my vote.",                                                                  "phase": "Deliberation"},
            {"agent": "Foreperson", "text": "Round 2: 4 Not Guilty, 0 Guilty. Unanimous verdict reached.",                                                                                                                          "phase": "Deliberation"},
            # ── Verdict ──
            {"agent": "Bailiff",    "text": "All rise for the reading of the verdict.",                                                                                                                                              "phase": "Verdict"},
            {"agent": "Judge",      "text": "On the charge of Grand Theft Auto, the defendant Marcus Webb is found NOT GUILTY. Court is adjourned.",                                                                                 "phase": "Verdict"},
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
            {"agent": "Bailiff",    "text": "All rise. The Honorable Justice Park presiding. This civil proceeding is now in session.",                                                                                                                          "phase": "Opening"},
            {"agent": "Judge",      "text": "You may be seated. Nexus Corporation versus Aether Laboratories — alleged breach of NDA. Are plaintiff and defense counsel prepared to proceed?",                                                                    "phase": "Opening"},
            {"agent": "Prosecutor", "text": "Plaintiff's counsel is ready, Your Honor.",                                                                                                                                                                         "phase": "Opening"},
            {"agent": "Defense",    "text": "Defense is ready, Your Honor.",                                                                                                                                                                                     "phase": "Opening"},
            {"agent": "Judge",      "text": "Plaintiff's counsel, you may proceed with your opening statement.",                                                                                                                                                 "phase": "Opening"},
            {"agent": "Prosecutor", "text": "Nexus entrusted Aether with proprietary schematics under a clear NDA. Within six months, those schematics appeared in a PowerCell product. The documents will show this was deliberate.",                          "phase": "Opening"},
            {"agent": "Defense",    "text": "Aether's technology was developed independently. The NDA is vague and does not cover the engineering principles Aether shared. This is a competitor afraid of innovation.",                                         "phase": "Opening"},
            {"agent": "System",     "text": "— Evidence Presentation —",                                                                                                                                                                                        "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "Plaintiff submits Exhibit A: the signed NDA — clause: 'all technical specifications shared during the partnership are confidential.'",                                                                              "phase": "Evidence"},
            {"agent": "Judge",      "text": "Exhibit A admitted.",                                                                                                                                                                                               "phase": "Evidence"},
            {"agent": "Prosecutor", "text": "Plaintiff submits Exhibit B: email from Aether CTO to PowerCell attaching 'NX-Battery-Specs-v3.pdf'.",                                                                                                             "phase": "Evidence"},
            {"agent": "Defense",    "text": "Objection. File name alone does not prove contents are Nexus IP. Independent expert verification is required.",                                                                                                     "phase": "Evidence"},
            {"agent": "Judge",      "text": "Sustained in part. Email admitted; file contents require expert verification. FRE 1002.",                                                                                                                           "phase": "Evidence"},
            {"agent": "System",     "text": "— Witness Examination —",                                                                                                                                                                                          "phase": "Witness"},
            {"agent": "Prosecutor", "text": "Plaintiff calls Dr. Helen Marsh, Nexus materials engineer. Dr. Marsh — did you compare PowerCell's product to your schematics?",                                                                                   "phase": "Witness"},
            {"agent": "Witness",    "text": "Yes. The cathode layering pattern in PowerCell's product is a 94% structural match to our NX-7 design, shared with Aether under NDA.",                                                                             "phase": "Witness"},
            {"agent": "Defense",    "text": "Dr. Marsh — isn't cathode layering a well-known industry technique? Couldn't PowerCell have arrived at a similar design independently?",                                                                           "phase": "Witness"},
            {"agent": "Witness",    "text": "The general technique is known. But the specific thickness ratios and dopant sequence are unique to our process. I know of no published literature describing this exact combination.",                               "phase": "Witness"},
            {"agent": "Fact Checker", "text": "✓ Testimony is within deposition scope. Claims are documented.",                                                                                                                                                 "phase": "Witness"},
            {"agent": "System",     "text": "— Closing Arguments —",                                                                                                                                                                                            "phase": "Closing"},
            {"agent": "Prosecutor", "text": "94% structural match. Emails with Nexus file names. A signed NDA. The breach is clear.",                                                                                                                           "phase": "Closing"},
            {"agent": "Defense",    "text": "A file name is not proof. The NDA is vague. A 94% match in an iterative industry is not a smoking gun.",                                                                                                           "phase": "Closing"},
            {"agent": "System",     "text": "— Jury Deliberation —",                                                                                                                                                                                            "phase": "Deliberation"},
            {"agent": "Judge",      "text": "Jury — determine by a preponderance of evidence whether Aether Labs breached the NDA.",                                                                                                                             "phase": "Deliberation"},
            {"agent": "Foreperson", "text": "Initial positions, please.",                                                                                                                                                                                        "phase": "Deliberation"},
            {"agent": "Juror",      "text": "Juror #1 (Analytical): Liable. 94% match plus the email is damning.",                                                                                                                                              "phase": "Deliberation"},
            {"agent": "Juror",      "text": "Juror #2 (Skeptical): Liable. The file was literally named 'NX-Battery-Specs'.",                                                                                                                                   "phase": "Deliberation"},
            {"agent": "Juror",      "text": "Juror #3 (Empathetic): Liable. An NDA is an NDA.",                                                                                                                                                                 "phase": "Deliberation"},
            {"agent": "Juror",      "text": "Juror #4 (Pragmatic): Not Liable. The NDA wording is genuinely vague.",                                                                                                                                            "phase": "Deliberation"},
            {"agent": "Foreperson", "text": "Round 1: 3 Liable, 1 Not Liable. Juror #4?",                                                                                                                                                                      "phase": "Deliberation"},
            {"agent": "Juror",      "text": "Juror #4: The email tips it. If the file wasn't proprietary, why name it after Nexus specs? Changing to Liable.",                                                                                                  "phase": "Deliberation"},
            {"agent": "Foreperson", "text": "Round 2: 4 Liable, 0 Not Liable. Unanimous.",                                                                                                                                                                      "phase": "Deliberation"},
            {"agent": "Bailiff",    "text": "All rise for the reading of the verdict.",                                                                                                                                                                          "phase": "Verdict"},
            {"agent": "Judge",      "text": "The jury finds Aether Labs LIABLE for breach of NDA. Damages to be assessed at a separate hearing. Court adjourned.",                                                                                              "phase": "Verdict"},
        ],
        "verdict": "LIABLE",
        "win_probability": 0.82,
        "sensitivity": "If the email had been excluded → Plaintiff win probability drops to 41%",
        "shadow_jury_narrative": [
            {"name": "Shadow Juror 1", "content": "The email with file name 'NX-Battery-Specs-v3.pdf' is damning. Combined with the 94% structural match, this is clear breach. [Vote: Liable]"},
            {"name": "Shadow Juror 2", "content": "The NDA explicitly covers 'all technical specifications.' Aether shared them with PowerCell. The intent is evident from the email. [Vote: Liable]"},
            {"name": "Shadow Juror 3", "content": "While cathode layering is known industry technique, the specific thickness ratios are proprietary. The match is too precise to be coincidence. [Vote: Liable]"},
            {"name": "Shadow Juror 4", "content": "The NDA wording could be clearer, but the email shows Aether knew the information was confidential. They proceeded anyway. [Vote: Liable]"},
            {"name": "Shadow Juror 5", "content": "Independent development is a weak defense when the file was literally named after Nexus's internal designation. [Vote: Liable]"},
        ],
    },
}
