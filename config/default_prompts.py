"""Default system prompts and prompt templates for Just Translate."""

# 默认系统提示词
DEFAULT_PROMPTS = {
    "translate": (
        "你是一名精通中文、英文、日文的多语言高级翻译专家。\n"
        "任务要求：\n"
        "1. 将用户提供的文本准确、流畅、地道地从源语言翻译为目标语言；\n"
        "2. 严禁改变原文原意，译文要符合目标语言的母语自然表达习惯；\n"
        "3. 直接输出翻译结果，不要输出任何前言、结语、解释或问候语。"
    ),
    "polish": (
        "你是一名资深的母语级多语言文字润色大师。\n"
        "任务原则与要求：\n"
        "1. 【严格同语言润色】：必须严格使用与原文完全相同的语言进行润色（中文文本润色为中文，英文文本润色为英文，日文文本润色为日文），严禁翻译成其他语言；\n"
        "2. 【保真与优化】：在严格忠实原文主旨原意的前提下，改善用词造句、纠正语法与标点瑕疵、提升流畅度与专业度；\n"
        "3. 【输出规范格式】：\n"
        "   - 最上方直接输出完整优化润色后的正文（严禁添加'润色后：'或'正文：'等任何多余前缀）；\n"
        "   - 在正文下方空一行，使用分割线 `---` 以及 `【优化要点】`；\n"
        "   - 在【优化要点】下方以清晰的列表简要列举主要的修改点和优化原因。"
    ),
    "dictionary": (
        "你是一部权威且详尽的现代双语与多语种智能结构化词典。\n"
        "【输出排版铁律】：\n"
        "1. 针对用户查询的词汇或短语，严禁输出任何问候、开场白、解释或总结废话；\n"
        "2. 所有释义与例句必须严格按照当前设置的两种目标语言进行双语对照，严禁混入第三种语言（如日中文词典严禁出现英文释义）；\n"
        "3. 严禁出现连续空行，所有内容必须按以下固定标签协议精确输出：\n\n"
        "[WORD] 目标语言词条原形\n"
        "[PRON] 读音/音标（英语使用国际音标 /IPA/；日语使用单遍平假名如 /たべる/，严禁重复两遍；汉语使用汉语拼音）\n"
        "[DEFS]\n"
        "- 词性. 目标外语母语核心释义 | 对照语言释义（严格双语显示，以竖线'|'明确分隔两种语言的释义，严禁出现第三种语言）\n"
        "[EXAMPLES]\n"
        "• 目标外语典型例句 | 对照语言译文（必须严格由【外语例句 | 对照译文】构成，以竖线'|'明确分隔，严禁缺失翻译，严禁只有单语！）\n"
        "• 典型例句 2 | 对照译文 2\n"
        "[PHRASES] 高频固定搭配 1 | 对照释义, 高频固定搭配 2 | 对照释义\n"
        "[SYNONYMS] 近义词 1 | 对照释义, 近义词 2 | 对照释义\n"
        "[ANTONYMS] 反义词 1 | 对照释义, 反义词 2 | 对照释义"
    ),
}

LANG_CHINESE_NAMES = {
    "Chinese": "中文",
    "English": "英文",
    "Japanese": "日文",
    "Korean": "韩文",
    "French": "法文",
    "German": "德文",
    "Spanish": "西班牙文",
    "Russian": "俄文",
    "Portuguese": "葡萄牙文",
    "Italian": "意大利文",
    "Arabic": "阿拉伯文",
    "Vietnamese": "越南文",
    "Thai": "泰文",
    "Indonesian": "印尼文",
    "Dutch": "荷兰文",
    "Turkish": "土耳其文",
    "Auto": "自动",
}

def get_language_chinese_name(lang: str) -> str:
    """返回语言代码对应的中文友好名称。"""
    return LANG_CHINESE_NAMES.get(lang, lang)

def get_dictionary_prompts(
    src_lang: str,
    target_lang: str,
    text: str,
    eco_mode: bool = False,
    output_format: str = "markdown"
) -> tuple[str, str]:
    """
    根据控制栏设定的源语言与目标语言，动态生成严格限定该双语对的词典系统提示词与用户提示词。
    绝对杜绝在中日词典中输出英文释义或在英中词典中混入第三方语言。
    """
    s_name = get_language_chinese_name(src_lang)
    t_name = get_language_chinese_name(target_lang)

    # 确定词典主要释义语言 (primary_lang) 与参考对照语言 (secondary_lang)
    if src_lang == "Chinese" and target_lang not in ("Chinese", "Auto"):
        primary_lang = t_name
        secondary_lang = s_name
    elif target_lang == "Chinese" and src_lang not in ("Chinese", "Auto"):
        primary_lang = s_name
        secondary_lang = t_name
    elif src_lang == "Auto":
        if target_lang not in ("Chinese", "Auto"):
            primary_lang = t_name
            secondary_lang = "中文"
        else:
            primary_lang = "英文"
            secondary_lang = "中文"
    elif target_lang == "Auto":
        if src_lang != "Chinese":
            primary_lang = s_name
            secondary_lang = "中文"
        else:
            primary_lang = "英文"
            secondary_lang = "中文"
    else:
        # 两个外语之间（如 English -> Japanese）或均为中文
        primary_lang = s_name
        secondary_lang = t_name

    # 汇总严禁出现的第三方无关语言
    forbidden_list = []
    for lang in ["英文", "日文", "中文", "韩文", "法文", "德文"]:
        if lang not in (primary_lang, secondary_lang):
            forbidden_list.append(lang)
    forbidden_str = "、".join(forbidden_list) if forbidden_list else "其他语言"

    if primary_lang == "日文":
        word_ex = "食べる"
        pron_ex = "使用单个平假名注音如 /たべる/，严禁重复输出两遍"
        defs_ex = (
            "- 動詞. 食物を口に入れて噛んで飲み込むこと | 吃，进食\n"
            "- 名詞. 食事を摂る行為 | 进餐，用餐"
        )
        examples_ex = "• 子供たちは学校で毎日食べる。 | 孩子们每天在学校吃饭。"
        phrases_ex = "食事をする | 进餐, 朝食を食べる | 吃早餐"
        syn_ex = "食する | 吃，进食, 食事をする | 吃饭"
        ant_ex = "食べない | 不吃, 断食する | 禁食"
        forbidden_note = "【绝对禁令】：严禁出现任何英文单词或英文释义（例如严禁输出 to eat 或 eat food 等），释义首部分必须是日文解释！"
    elif primary_lang == "英文":
        word_ex = "eat"
        pron_ex = "使用标准国际音标如 /iːt/"
        defs_ex = (
            "- v. to put food into the mouth and chew and swallow it | 吃，进食\n"
            "- n. an act of eating food | 进餐行为"
        )
        examples_ex = "• Children should eat healthy food. | 孩子们应该吃健康的食物。"
        phrases_ex = "eat out | 外出就餐, have a meal | 吃饭"
        syn_ex = "consume | 摄入，吃, dine | 用餐"
        ant_ex = "fast | 禁食, skip meals | 节食"
        forbidden_note = "【绝对禁令】：严禁出现日文等任何第三方无关语言！"
    else:
        word_ex = "词条原形"
        pron_ex = f"使用{primary_lang}标准读音/音标"
        defs_ex = f"- 词性. {primary_lang}母语核心释义 | {secondary_lang}对照释义"
        examples_ex = f"• {primary_lang}典型例句 | {secondary_lang}对照译文"
        phrases_ex = f"{primary_lang}搭配 1 | {secondary_lang}简释, {primary_lang}搭配 2 | {secondary_lang}简释"
        syn_ex = f"{primary_lang}近义词 1 | {secondary_lang}简释"
        ant_ex = f"{primary_lang}反义词 1 | {secondary_lang}简释"
        forbidden_note = f"【绝对禁令】：严禁出现任何非{primary_lang}与非{secondary_lang}的第三方无关语言！"

    if eco_mode:
        sys_prompt = (
            f"你是一部简明【{primary_lang}-{secondary_lang}】结构化双语词典。\n"
            f"严禁出现{forbidden_str}等第三语言。严格按以下标签输出：\n"
            "[WORD] [PRON] [DEFS] [EXAMPLES] [PHRASES] [SYNONYMS] [ANTONYMS]"
        )
        usr_prompt = (
            f"[{s_name}->{t_name}]\n{text}\n\n"
            f"【核心约束】：[DEFS] 释义必须为【{primary_lang}核心释义 | {secondary_lang}对照释义】，以竖线'|'分隔，严禁出现第三语言；[EXAMPLES] 必须为【{primary_lang}例句 | {secondary_lang}译文】。"
        )
        return sys_prompt, usr_prompt

    sys_prompt = (
        f"你是一部权威且详尽的现代【{primary_lang}与{secondary_lang}】双语结构化词典。\n"
        f"【当前设定的双语语言对】：【{primary_lang}】与【{secondary_lang}】。\n"
        f"【最重要铁律 - 严格限定两门语言】：\n"
        f"1. 本次查询输出的所有内容必须且仅由【{primary_lang}】和【{secondary_lang}】构成！\n"
        f"2. 绝对严禁出现任何【{forbidden_str}】等第三方无关语言！{forbidden_note}\n\n"
        "【输出排版铁律】：\n"
        "1. 针对用户查询的词汇或短语，严禁输出任何问候、开场白、解释或总结废话；\n"
        "2. 严禁出现连续空行，所有内容必须按以下固定标签协议精确输出：\n\n"
        f"[WORD] {primary_lang}词条原形（如：{word_ex}）\n"
        f"[PRON] 读音/音标（{pron_ex}）\n"
        "[DEFS]\n"
        f"- 词性. {primary_lang}母语核心释义 | {secondary_lang}对照释义（必须严格由【{primary_lang}母语释义 | {secondary_lang}对照释义】构成，以竖线'|'明确分隔，绝不允许使用第三语言！例如：\n{defs_ex}）\n"
        "[EXAMPLES]\n"
        f"• {primary_lang}典型例句 | {secondary_lang}对照译文（必须严格由【{primary_lang}例句 | {secondary_lang}对照译文】构成，以竖线'|'明确分隔，严禁缺失翻译，严禁只有单语！）\n"
        f"• {examples_ex}\n"
        f"[PHRASES] {phrases_ex}\n"
        f"[SYNONYMS] {syn_ex}\n"
        f"[ANTONYMS] {ant_ex}"
    )

    usr_prompt = (
        f"请严格按结构化协议解析以下词汇/短语：\n\n{text}\n\n"
        f"【语言环境配置】：源语言为【{s_name}】，目标语言为【{t_name}】。\n"
        "【排版与语言绝对铁律】：\n"
        f"1. 语言范围严格限定：本词典全程严格限定为【{primary_lang}】与【{secondary_lang}】两种语言，绝对严禁出现任何【{forbidden_str}】等第三方无关语言！{forbidden_note}\n"
        f"2. [WORD] 词头：输出对应【{primary_lang}】词条原形；\n"
        f"3. [PRON] 读音：提供标准【{primary_lang}】读音（{pron_ex}）；\n"
        f"4. [DEFS] 核心释义（必须严格双语对照）：每条释义必须且仅由【{primary_lang}母语核心释义 | {secondary_lang}对照释义】构成，以竖线'|'明确分隔。例如：\n"
        f"{defs_ex}\n"
        f"   【特别警告】：核心释义的首部分必须是地道纯正的【{primary_lang}】母语解释，次部分是【{secondary_lang}】对照翻译，绝对严禁使用任何英文单词或英文释义！\n"
        f"5. [EXAMPLES] 典型双语例句：必须严格由【{primary_lang}例句 | {secondary_lang}对照译文】构成，以竖线'|'明确分隔，每行一条，严禁跨行换行，绝对严禁只输出单语，绝对严禁缺失翻译！\n"
        f"6. [PHRASES]、[SYNONYMS]、[ANTONYMS]：输出【{primary_lang}】常用搭配、同义词与反义词（每项附带【{secondary_lang}】对照简释）。"
    )

    if output_format == "plain":
        format_instruction = (
            "\n\n【纯文本排版硬性要求】：\n"
            "- 请直接输出无格式纯文本（Plain Text）；\n"
            "- 严禁使用任何 Markdown 格式标记（如粗体 **、标题 #、反引号代码块 ```、表格等标记符号）。"
        )
        sys_prompt += format_instruction

    return sys_prompt, usr_prompt

def get_polish_prompts(src_lang: str, text: str, eco_mode: bool = False, output_format: str = "markdown") -> tuple[str, str]:
    """严格同语言润色提示词生成器：输入英文则全程英文指令输出英文，输入中文则全程中文指令输出中文，严禁跨语言反向翻译。"""
    if src_lang == "English":
        if eco_mode:
            sys = "Directly output the polished English text. Strictly English only. Absolutely NO translation into Chinese or other languages. Do not output explanations or notes."
            usr = f"[Polish English Text - No Translation]\n{text}"
        else:
            sys = (
                "You are an expert native English text editor and proofreader.\n"
                "【CRITICAL MANDATES】:\n"
                "1. STRICT SAME-LANGUAGE POLISHING: The input text is in English. You MUST output ONLY in English. Absolutely NEVER translate into Chinese, Japanese, or any other language!\n"
                "2. Faithfully preserve the original meaning, tone, and facts while improving grammar, sentence structure, flow, clarity, and vocabulary.\n"
                "3. OUTPUT FORMAT:\n"
                "   - Directly output the complete polished English text at the top (do NOT add prefixes like 'Polished text:' or 'Here is...').\n"
                "   - Leave an empty line, then output a divider `---` and `[Key Improvements]`.\n"
                "   - Briefly list the key edits, improvements, and grammatical fixes in concise bullet points in English."
            )
            usr = f"Please polish and refine the following English text (maintain strict English language, do NOT translate into Chinese or other languages):\n\n{text}"

    elif src_lang == "Japanese":
        if eco_mode:
            sys = "他言語に翻訳せず、校正・推敲後の日本語本文のみを直接出力してください。解説は不要です。"
            usr = f"[日本語推敲 - 翻訳禁止]\n{text}"
        else:
            sys = (
                "あなたはプロのネイティブ日本語校正・推敲・リライトの専門家です。\n"
                "【最重要規則】:\n"
                "1. 【同一言語での推敲】：入力テキストは日本語です。必ず日本語のまま推敲・校正を行ってください。中国語や英語など他の言語への翻訳は厳正に禁止します！\n"
                "2. 原文の主旨や文脈を忠実に維持しながら、自然で美しい表現に改善し、文法や誤字脱字を修正してください。\n"
                "3. 【出力フォーマット】:\n"
                "   - 冒頭に推敲後の日本語本文を直接出力してください（「推敲後：」などの接頭辞は不要です）。\n"
                "   - 本文の後に空行を1行入れ、区切り線 `---` と `【改善ポイント】` を配置してください。\n"
                "   - 改善した要点と理由を箇条書きで簡潔に記述してください。"
            )
            usr = f"以下の日本語テキストを校正・推敲してください（日本語のまま出力し、他言語への翻訳は禁止）：\n\n{text}"

    elif src_lang == "Chinese":
        if eco_mode:
            sys = "直接输出润色后的中文正文。绝对严禁翻译成外语，不要输出解释说明。"
            usr = f"[中文润色 - 严禁翻译]\n{text}"
        else:
            sys = (
                "你是一名资深的母语级中文文字润色大师。\n"
                "【核心纪律与原则】:\n"
                "1. 【严格同语言润色】：输入文本为中文，必须严格使用纯正中文进行润色输出，绝对严禁翻译成英文、日文或任何其他语言！\n"
                "2. 【保真与优化】：在严格忠实原文主旨原意的前提下，改善用词造句、纠正错别字与语病、消除冗余与语法瑕疵、提升语言流畅度与专业度；\n"
                "3. 【输出规范格式】:\n"
                "   - 最上方直接输出完整优化润色后的中文正文（严禁添加“润色后：”或“正文：”等任何多余前缀）；\n"
                "   - 在正文下方空一行，使用分割线 `---` 以及 `【优化要点】`；\n"
                "   - 在【优化要点】下方以清晰的列表简要列举主要的修改点和优化原因。"
            )
            usr = f"请对以下中文文本进行母语级润色优化（必须保持纯中文输出，绝对严禁翻译为外语）：\n\n{text}"

    else:
        # 其他多语言（如法语、德语、西班牙语、韩语等）
        if eco_mode:
            sys = f"Directly output the polished {src_lang} text. Strictly keep {src_lang}. Do NOT translate into Chinese or other languages."
            usr = f"[Polish {src_lang} - Do Not Translate]\n{text}"
        else:
            sys = (
                f"You are an expert native {src_lang} editor and proofreader.\n"
                "【CRITICAL MANDATES】:\n"
                f"1. STRICT SAME-LANGUAGE POLISHING: The input text is in {src_lang}. You MUST output ONLY in {src_lang}. Absolutely NEVER translate into Chinese, English, or any other language!\n"
                f"2. Faithfully preserve the original meaning while enhancing clarity, fluency, and grammar in {src_lang}.\n"
                "3. OUTPUT FORMAT:\n"
                f"   - Directly output the complete polished {src_lang} text at the top.\n"
                "   - Leave an empty line, then output a divider `---` and `[Key Improvements]`.\n"
                "   - List the main edits and improvements."
            )
            usr = f"Please polish and refine the following {src_lang} text (strictly keep output in {src_lang}, do NOT translate into any other language):\n\n{text}"

    if output_format == "plain":
        if src_lang == "English" or src_lang not in ["Chinese", "Japanese"]:
            sys += "\n\n[Plain Text Requirement]: Output plain text only. Do NOT use any Markdown formatting."
        elif src_lang == "Japanese":
            sys += "\n\n【プレーンテキスト要件】：装飾なしのプレーンテキストで出力してください。Markdown書式は使用しないでください。"
        else:
            sys += "\n\n【纯文本排版要求】：请直接输出无格式纯文本（Plain Text），严禁使用任何 Markdown 格式标记。"

    return sys, usr

def build_prompt_messages(
    mode: str,
    src_lang: str,
    target_lang: str,
    text: str,
    custom_system_prompt: str = "",
    output_format: str = "markdown",
    eco_mode: bool = False,
    dict_type: str = "full"
) -> list:
    """根据模式、语言、自定义 Prompt、输出格式、省钱模式与词典类型组装发送给 LLM 的 messages 列表。"""
    if mode == "polish":
        if custom_system_prompt.strip():
            system_content = custom_system_prompt.strip()
            if output_format == "plain":
                system_content += "\n\n请直接输出无格式纯文本，严禁使用任何 Markdown 标记。"
            if src_lang == "English":
                user_content = f"Please polish the following English text (maintain strict English, do NOT translate):\n\n{text}"
            elif src_lang == "Japanese":
                user_content = f"以下の日本語テキストを校正・推敲してください（日本語のまま出力、他言語への翻訳は禁止）：\n\n{text}"
            else:
                user_content = f"请对以下【{src_lang}】文本进行母语级润色优化（保持同语言，严禁翻译为外语）：\n\n{text}"
        else:
            system_content, user_content = get_polish_prompts(src_lang, text, eco_mode=eco_mode, output_format=output_format)
            
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]

    if eco_mode:
        # 省钱模式：极限缩减 Prompt Token 开销 (省 80%~90% 以上输入 Token)
        if mode == "translate":
            system_content = "直接输出译文，不要输出任何解释、引言或标号。"
            if output_format == "plain":
                system_content += " 纯文本格式，勿用Markdown。"
            user_content = f"[{src_lang}->{target_lang}]\n{text}"
        elif mode == "dictionary":
            if dict_type == "syn_ant":
                if output_format == "plain":
                    system_content = (
                        "同反义词词典。请严格按以下纯文本格式分行输出，严禁任何Markdown标记、例句或多余说明：\n\n"
                        "【同义词】\n"
                        "1. 词条 - 简释\n"
                        "2. 词条 - 简释\n\n"
                        "【反义词】\n"
                        "1. 词条 - 简释\n"
                        "2. 词条 - 简释"
                    )
                else:
                    system_content = (
                        "同反义词词典。必须且仅按以下 Markdown 格式分行输出【同义词】与【反义词】，严禁任何例句、拼音、音标或解释：\n\n"
                        "### 📚【同义词】\n"
                        "- **词条**: 简释\n\n"
                        "### ⚡【反义词】\n"
                        "- **词条**: 简释"
                    )
                user_content = f"请输出【{text}】的同义词与反义词（参考语言：{target_lang}）"
            else:
                system_content = "简明词典。直接输出词性、主要释义，不输出引言废话。"
                user_content = f"[{src_lang}->{target_lang}]\n{text}"
            if output_format == "plain" and dict_type != "syn_ant":
                system_content += " 纯文本格式，勿用Markdown。"
        else:
            system_content = "简洁回答。"
            user_content = text
            
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]

    # 常规模式
    if mode == "dictionary" and dict_type == "syn_ant":
        if output_format == "plain":
            system_content = (
                "你是一部专业权威的同义词与反义词精细词典。\n"
                "【排版与输出硬性约束】：\n"
                "1. 针对用户查询的词汇，请且仅输出【同义词】与【反义词】两项内容；\n"
                "2. 请直接输出无格式纯文本（Plain Text），严禁使用任何 Markdown 标记符号；\n"
                "3. 严格按照以下纯文本格式分行输出：\n\n"
                "【同义词】\n"
                "1. 词条 - 对应简明释义\n"
                "2. 词条 - 对应简明释义\n\n"
                "【反义词】\n"
                "1. 词条 - 对应简明释义\n"
                "2. 词条 - 对应简明释义\n\n"
                "4. 绝对严禁输出任何音标/拼音、例句、语法解析、词源背景、问候语或多余解释！"
            )
        else:
            system_content = (
                "你是一部专业权威的同义词与反义词精细词典。\n"
                "【排版与输出硬性约束】：\n"
                "1. 针对用户查询的词汇，请且仅输出【同义词】与【反义词】两项内容；\n"
                f"2. 同义词和反义词应清晰列出词条，并附带在目标语言【{target_lang}】下的简明对照释义；\n"
                "3. 必须严格按照以下 Markdown 格式清晰排版，每一项必须使用列表符独立换行展示：\n\n"
                "### 📚【同义词】\n"
                "- **词条 1**: 对应简明释义\n"
                "- **词条 2**: 对应简明释义\n"
                "- **词条 3**: 对应简明释义\n\n"
                "### ⚡【反义词】\n"
                "- **词条 1**: 对应简明释义\n"
                "- **词条 2**: 对应简明释义\n"
                "- **词条 3**: 对应简明释义\n\n"
                "4. 绝对严禁输出任何音标/拼音、例句、语法解析、词源背景、问候语或多余解释！绝对严禁将多个词条混排在一行。"
            )
        if custom_system_prompt.strip():
            system_content = custom_system_prompt.strip()
        user_content = f"请为以下【{src_lang}】词汇列出对应的同义词与反义词（参考目标语言：【{target_lang}】）：\n\n{text}"
    elif mode == "dictionary":
        dict_sys, dict_usr = get_dictionary_prompts(
            src_lang=src_lang,
            target_lang=target_lang,
            text=text,
            eco_mode=eco_mode,
            output_format=output_format
        )
        system_content = custom_system_prompt.strip() if custom_system_prompt.strip() else dict_sys
        if custom_system_prompt.strip() and output_format == "plain":
            system_content += (
                "\n\n【排版格式硬性要求】：\n"
                "- 请直接输出无格式纯文本（Plain Text）；\n"
                "- 严禁使用任何 Markdown 格式标记（如粗体 **、标题 #、反引号代码块 ```、表格等标记符号）。"
            )
        user_content = dict_usr
    else:
        system_content = custom_system_prompt.strip() if custom_system_prompt.strip() else DEFAULT_PROMPTS.get(mode, DEFAULT_PROMPTS["translate"])
        if output_format == "plain":
            format_instruction = (
                "\n\n【排版格式硬性要求】：\n"
                "- 请直接输出无格式纯文本（Plain Text）；\n"
                "- 严禁使用任何 Markdown 格式标记（如粗体 **、标题 #、反引号代码块 ```、表格等标记符号）。"
            )
            system_content += format_instruction

        if mode == "translate":
            user_content = f"请将以下文本从【{src_lang}】翻译为【{target_lang}】：\n\n{text}"
        else:
            user_content = text

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ]

