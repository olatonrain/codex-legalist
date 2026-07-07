# ── Agent Model Configuration ───────────────────────────────────
# Specify the model for each agent. Options: "qwen-max", "qwen-plus-latest", "qwen-flash", "qwen-turbo-latest"

AGENT_MODELS = {
    "Magistrate":      "qwen-max",
    "Judge":           "qwen-max",
    "Prosecutor":      "qwen-plus-latest",
    "Defense Counsel": "qwen-plus-latest",
    "Witness":         "qwen-flash",
    "Fact Checker":    "qwen-plus-latest",
    "Clerk":           "qwen-flash",
    "Archivist":       "qwen-turbo-latest",
    "Jury Foreperson": "qwen-plus-latest"
}

# ── Jurisdiction Registry ────────────────────────────────────────
# Maps country → procedural and evidentiary rules for that jurisdiction.
# "procedure":  "adversarial" (common law) or "inquisitorial" (civil law)
# "jury":       True if jury trials are standard; False if bench/panel trials
# "cross":      True if opposing counsel cross-examines; False if judge questions
# "address":    How to address the presiding judge in court

JURISDICTIONS = {
    # ── Common Law (Adversarial) ─────────────────────────────────
    "United Kingdom": {
        "system": "Common Law",
        "procedure": "adversarial",
        "criminal_standard": "Beyond reasonable doubt",
        "civil_standard": "Balance of probabilities",
        "evidence_rules": "Police and Criminal Evidence Act 1984 (PACE); Criminal Procedure Rules 2020",
        "jury": True,
        "cross": True,
        "address": "My Lord / My Lady (High Court); Your Honour (Crown Court)",
        "flag": "🇬🇧",
    },
    "United States": {
        "system": "Common Law",
        "procedure": "adversarial",
        "criminal_standard": "Beyond a reasonable doubt",
        "civil_standard": "Preponderance of the evidence",
        "evidence_rules": "Federal Rules of Evidence (FRE); Federal Rules of Criminal Procedure",
        "jury": True,
        "cross": True,
        "address": "Your Honor",
        "flag": "🇺🇸",
    },
    "Nigeria": {
        "system": "Common Law",
        "procedure": "adversarial",
        "criminal_standard": "Beyond reasonable doubt",
        "civil_standard": "Balance of probabilities",
        "evidence_rules": "Evidence Act 2011; Administration of Criminal Justice Act 2015 (ACJA)",
        "jury": False,  # Nigeria abolished jury trials
        "cross": True,
        "address": "My Lord / Your Lordship (High Court); Your Worship (Magistrate Court)",
        "flag": "🇳🇬",
    },
    "Ghana": {
        "system": "Common Law",
        "procedure": "adversarial",
        "criminal_standard": "Beyond reasonable doubt",
        "civil_standard": "Balance of probabilities",
        "evidence_rules": "Evidence Act 1975 (NRCD 323); Courts Act 1993",
        "jury": False,
        "cross": True,
        "address": "My Lord / Your Lordship",
        "flag": "🇬🇭",
    },
    "Kenya": {
        "system": "Common Law",
        "procedure": "adversarial",
        "criminal_standard": "Beyond reasonable doubt",
        "civil_standard": "Balance of probabilities",
        "evidence_rules": "Evidence Act (Cap. 80); Criminal Procedure Code (Cap. 75)",
        "jury": False,
        "cross": True,
        "address": "My Lord / Your Honour",
        "flag": "🇰🇪",
    },
    "South Africa": {
        "system": "Mixed (Common Law + Roman-Dutch)",
        "procedure": "adversarial",
        "criminal_standard": "Beyond reasonable doubt",
        "civil_standard": "Balance of probabilities",
        "evidence_rules": "Criminal Procedure Act 51 of 1977; Law of Evidence Amendment Act 45 of 1988",
        "jury": False,  # SA abolished jury trials in 1969
        "cross": True,
        "address": "My Lord / My Lady (High Court); Your Worship (Magistrate)",
        "flag": "🇿🇦",
    },
    "Australia": {
        "system": "Common Law",
        "procedure": "adversarial",
        "criminal_standard": "Beyond reasonable doubt",
        "civil_standard": "Balance of probabilities",
        "evidence_rules": "Evidence Act 1995 (Cth); Uniform Evidence Law",
        "jury": True,
        "cross": True,
        "address": "Your Honour",
        "flag": "🇦🇺",
    },
    "Canada": {
        "system": "Common Law",
        "procedure": "adversarial",
        "criminal_standard": "Beyond a reasonable doubt",
        "civil_standard": "Balance of probabilities",
        "evidence_rules": "Canada Evidence Act (R.S.C. 1985, c. C-5); Criminal Code of Canada",
        "jury": True,
        "cross": True,
        "address": "Your Honour / My Lord",
        "flag": "🇨🇦",
    },
    "India": {
        "system": "Common Law",
        "procedure": "adversarial",
        "criminal_standard": "Beyond reasonable doubt",
        "civil_standard": "Preponderance of probabilities",
        "evidence_rules": "Bharatiya Sakshya Adhiniyam 2023 (formerly Indian Evidence Act 1872); BNSS 2023",
        "jury": False,  # India abolished jury trials after 1961
        "cross": True,
        "address": "My Lord / Your Lordship / Your Honour",
        "flag": "🇮🇳",
    },
    "Jamaica": {
        "system": "Common Law",
        "procedure": "adversarial",
        "criminal_standard": "Beyond reasonable doubt",
        "civil_standard": "Balance of probabilities",
        "evidence_rules": "Evidence Act (Jamaica); Judicature (Resident Magistrates) Act",
        "jury": True,
        "cross": True,
        "address": "Your Honour / My Lord",
        "flag": "🇯🇲",
    },
    # ── Civil Law (Inquisitorial) ─────────────────────────────────
    "France": {
        "system": "Civil Law",
        "procedure": "inquisitorial",
        "criminal_standard": "Intime conviction (inner conviction of the judge)",
        "civil_standard": "Intime conviction",
        "evidence_rules": "Code de procédure pénale; Code civil",
        "jury": False,  # Jury only for Cour d'assises (serious crimes); abolished for most cases
        "cross": False,  # Judge questions witnesses; parties may suggest questions
        "address": "Monsieur / Madame le Président",
        "flag": "🇫🇷",
    },
    "Germany": {
        "system": "Civil Law",
        "procedure": "inquisitorial",
        "criminal_standard": "Überzeugung des Richters (judge's personal conviction)",
        "civil_standard": "Überzeugung des Richters",
        "evidence_rules": "Strafprozessordnung (StPO); Zivilprozessordnung (ZPO)",
        "jury": False,
        "cross": False,
        "address": "Herr / Frau Vorsitzende (Presiding Judge)",
        "flag": "🇩🇪",
    },
    "Netherlands": {
        "system": "Civil Law",
        "procedure": "inquisitorial",
        "criminal_standard": "Wettige en overtuigende bewijzen (legal and convincing proof)",
        "civil_standard": "Overtuiging van de rechter",
        "evidence_rules": "Wetboek van Strafvordering; Wetboek van Burgerlijke Rechtsvordering",
        "jury": False,
        "cross": False,
        "address": "Edelachtbare (Honourable)",
        "flag": "🇳🇱",
    },
    "Brazil": {
        "system": "Civil Law",
        "procedure": "inquisitorial",
        "criminal_standard": "Convicção do juiz (judge's conviction)",
        "civil_standard": "Convicção do juiz",
        "evidence_rules": "Código de Processo Penal (CPP); Código de Processo Civil (CPC)",
        "jury": True,  # Jury for intentional crimes against life (dolosos contra a vida)
        "cross": False,
        "address": "Meritíssimo Juiz / Vossa Excelência",
        "flag": "🇧🇷",
    },
    "UAE": {
        "system": "Civil Law (with Islamic Law influence)",
        "procedure": "inquisitorial",
        "criminal_standard": "Judge's conviction based on evidence",
        "civil_standard": "Judge's conviction based on evidence",
        "evidence_rules": "Federal Penal Procedure Law No. 35 of 1992; Federal Civil Procedure Law",
        "jury": False,
        "cross": False,
        "address": "Your Excellency",
        "flag": "🇦🇪",
    },
    "Saudi Arabia": {
        "system": "Islamic Law (Sharia) + Royal Decrees",
        "procedure": "inquisitorial",
        "criminal_standard": "Judge's conviction; Quranic standards (e.g. Bayyina for Hudud)",
        "civil_standard": "Judge's conviction",
        "evidence_rules": "Law of Criminal Procedure 2001; Sharia principles",
        "jury": False,
        "cross": False,
        "address": "Your Excellency",
        "flag": "🇸🇦",
    },
    "China": {
        "system": "Socialist Legal System (with Civil Law characteristics)",
        "procedure": "inquisitorial",
        "criminal_standard": "Facts are clear, evidence is reliable and sufficient (事实清楚，证据确实充分)",
        "civil_standard": "Preponderance of evidence (高度盖然性)",
        "evidence_rules": "Criminal Procedure Law of the PRC (2018 Amendment); Civil Procedure Law of the PRC; Supreme People's Court Interpretations on Evidence",
        "jury": False,
        "cross": False,
        "address": "尊敬的审判长 (Respected Presiding Judge)",
        "flag": "🇨🇳",
    },
}

DEFAULT_COUNTRY = "Nigeria"

COUNTRY_LIST = sorted(JURISDICTIONS.keys())
