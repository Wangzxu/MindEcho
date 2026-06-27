# -*- coding: utf-8 -*-
import os
import json
import time
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

API_KEY = os.getenv("SILICONFLOW_API_KEY")
BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
# 使用 DeepSeek-V3 作为生成模型，性价比较高且指令遵循强
GENERATION_MODEL = "deepseek-ai/DeepSeek-V3"

# 24 种不同的性格与心理状态种子配置
SEEDS = [
    {
        "personality": "完美主义与学业压力型",
        "description": "用户往往是高敏感、完美主义者，有保研/考研同辈压力。总是自我怀疑，害怕在组会汇报或开学适应中落后。常用应对方式是跑步或跟好友（如小明）倾诉，但最近焦虑得静不下心。",
        "topics": ["组会汇报前极度焦虑", "保研到名校后的同辈学业压力"]
    },
    {
        "personality": "职场内耗与讨好型人格",
        "description": "工作超负荷但不敢拒绝领导/导师。习惯性讨好同事，有委屈和冲突自己默默忍受。常用吃甜食、买东西缓解压力，家庭中存在催婚的母亲（或其他带来焦虑的亲人）。",
        "topics": ["无法拒绝组里的杂活和无休止加班", "与导师或直属领导沟通时极度紧张"]
    },
    {
        "personality": "情感依恋焦虑型",
        "description": "亲密关系中极度缺乏安全感，对伴侣冷战极其敏感，总是过度自责，担心被抛弃。常用的应对方法是写日记或找闺蜜倾诉。关系网络中通常有其伴侣（如男友张三）。",
        "topics": ["伴侣冷战一整天引发慌张与胡思乱想", "因为伴侣回复微信慢产生强烈的自我怀疑"]
    },
    {
        "personality": "社交焦虑与退缩型",
        "description": "性格内向回避，害怕当众发言或进入新社交环境。过度担心被他人否定。常用抱猫（有一只叫喵喵的猫）或听纯音乐等逃避手段缓解压力。",
        "topics": ["新入职或入学自我介绍前极度紧张", "拒绝不了组委会聚餐引发严重精神内耗"]
    },
    {
        "personality": "易怒与路怒情绪失控型",
        "description": "极易因为日常琐事（如排队、水杯打翻、网络变慢）瞬间爆发狂躁愤怒，事后又感到自责。应对方式是深呼吸或摆弄解压魔方。身边有一只常安抚他情绪的金毛狗贝贝。",
        "topics": ["打翻水杯或排队过长时瞬间爆发狂躁愤怒", "堵车或赶路遇到慢行时产生毁灭性狂躁"]
    },
    {
        "personality": "慢性烦躁与精力涣散型",
        "description": "每天生活都感到莫名烦躁和无聊，无法集中注意力看书或学习，总是刷短视频但越刷越空虚。常用整理房间、拖地来转移注意力。关系网中有个经常唠叨和管教他的父亲。",
        "topics": ["无法集中注意力看书且刷手机倍感空虚", "每天都感到莫名烦躁且无所事事"]
    },
    {
        "personality": "强迫倾向与反复确认型",
        "description": "经常强迫性地反复确认锁门、拔插头、洗手，一旦步骤不对或者产生怀疑就会极度焦虑。通过整理书架或默数数字缓解。关系网中有同住的舍友小李。",
        "topics": ["出门前反复折返确认门锁与电器插头", "因为害怕弄脏双手而频繁强迫洗手"]
    },
    {
        "personality": "轻度抑郁与行动力丧失型",
        "description": "连续几天提不起精神，觉得生活索然无味，不想下床也不想洗漱，处于低能量状态。以前喜欢画画，现在连画笔都不想碰。关系网中有个经常发微信关心他的亲姐姐。",
        "topics": ["连续几天提不起精神只想躺在床上", "对曾经热爱的画画和音乐失去所有兴趣"]
    },
    {
        "personality": "健康焦虑与疑病倾向型",
        "description": "身体稍有微小不适（如偏头痛、偶发心慌、肌肉跳动）就坚信自己得了绝症。常用量血压、测量心率缓解，疯狂在网上查症状。关系网中有一位当医生的阿姨。",
        "topics": ["身体微小刺痛就坚信自己得了罕见绝症", "反复测量血压心率并疯狂在网上查症状"]
    },
    {
        "personality": "严重拖延与自我否定型",
        "description": "不到最后一刻绝不动手写作业或做汇报，拖延期间极度焦虑痛苦，做完后陷入自我厌恶。常用打游戏进行逃避。关系网中有一位非常严厉的导师王教授。",
        "topics": ["deadline前疯狂打游戏逃避做任务", "任务勉强完成后陷入疯狂自责并认为自己很废"]
    },
    {
        "personality": "习得性无助与放弃努力型",
        "description": "经历几次考试或面试失败后，觉得努力毫无用处，自己注定一事无成。常用蒙头大睡逃避现实。关系网中有一个总是拿他跟别人家孩子比较的母亲。",
        "topics": ["连续面试失败后坚信自己注定无药可救", "彻底放弃努力并觉得再怎么挣扎也改变不了结局"]
    },
    {
        "personality": "情感冷漠与冷暴力回避型",
        "description": "遇到人际或亲密关系冲突时下意识关闭情感，拒绝沟通，喜欢一个人呆着，觉得别人的情感需求很黏人、很烦。常用玩单机游戏解压。关系网中有一直在尝试和他沟通的追求者小红。",
        "topics": ["面对伴侣的情感沟通需求感到厌烦和想要逃跑", "发生人际误会时下意识采取冷暴力和自我封闭"]
    },
    {
        "personality": "情绪起伏大与轻躁狂交替型",
        "description": "情绪极其不稳定，前几天情绪高涨、精力过剩并疯狂消费，今天突然跌入谷底，连话都不想说。常用听摇滚乐释放。关系网中有非常包容和理解他的男友小高。",
        "topics": ["前几天极度亢奋疯狂消费而今天又悲观绝望", "情绪忽冷忽热让周围朋友感到无所适从"]
    },
    {
        "personality": "躯体化障碍与躯体焦虑型",
        "description": "一遇到压力（如考试、面试、社交）就会立刻出现胃痛、拉肚子、偏头痛、呼吸困难等躯体症状，去医院查不出任何器质性病变。常用喝温水或做拉伸缓解。关系网中有舍友默默的照顾。",
        "topics": ["一遇到考试就偏头痛和剧烈胃痛拉肚子", "精神紧绷时感到呼吸困难和胸闷气短"]
    },
    {
        "personality": "亲密关系过度占有与猜忌型",
        "description": "极其多疑，总是怀疑伴侣背叛自己，频繁想看对方手机，限制其正常社交。常用翻看对方聊天记录确认安全感。关系网中有极具耐心的女友小芳。",
        "topics": ["频繁翻看伴侣聊天记录以确认其没有背叛", "限制伴侣与任何异性同学进行社交往来"]
    },
    {
        "personality": "入睡困难与睡眠焦虑型",
        "description": "一躺下就忍不住开始大脑反刍，思考明天的安排或过去的尴尬事，越担心自己睡不着越清醒。常用白噪音或吃褪黑素缓解。关系网中有作息极好的舍友大强。",
        "topics": ["深夜躺下后疯狂大脑反刍导致严重失眠", "因为担心明天睡不够而越发焦虑和清醒"]
    },
    {
        "personality": "电子游戏与网瘾逃避型",
        "description": "一旦现实受挫（挂科、求职失败），就疯狂沉迷于网络或游戏，日夜颠倒以麻痹自我，但关掉电脑后空虚加倍。常用喝碳酸饮料解压。关系网中有常劝阻他健康生活的好哥们阿强。",
        "topics": ["挂科后靠连续打游戏12小时来麻痹自我", "用无休止刷短视频来逃避做毕业设计"]
    },
    {
        "personality": "创伤后应激敏感型",
        "description": "经历过特定人际创伤（如被当众霸凌、严厉责骂、车祸），对突发声音、激烈的争吵声、他人的冷漠表情极其敏感且容易受惊。常用戴降噪耳机来隔离外界。关系网中有关心他的心理咨询老师。",
        "topics": ["听到雷声或重物坠地声会瞬间惊恐颤抖", "被导师批评后脑海中不断回放童年被责骂的阴影"]
    },
    {
        "personality": "低自尊与自我厌恶型",
        "description": "强烈认为自己的身材、外貌或才华一无是处，不配得到任何好意，被赞美时感到极度恐慌和虚伪。常在半夜通过暴食缓解压力。关系网中有一个非常优秀且耀眼的亲妹妹。",
        "topics": ["面对别人的真诚赞美感到极其尴尬和配不上", "因为长相和身材缺陷产生强烈的自我厌恶"]
    },
    {
        "personality": "选择困难与决策焦虑型",
        "description": "哪怕是点什么外卖、买什么颜色的衣服等琐事都要纠结好几个小时，害怕做出错误的决策。常用抛硬币或让旁人做主。关系网中有个做事非常果断的好闺蜜婷婷。",
        "topics": ["点外卖纠结两个小时仍然无法做出选择", "站在选择的十字路口面对前途极其惊恐和瘫痪"]
    },
    {
        "personality": "述情障碍与情感表达困难型",
        "description": "内心波涛汹涌或极其难受，但在和别人沟通时无法用言语说清自己的情绪，只会本能说“很烦”。常用乱涂乱画或者写字划线发泄。关系网中有试图和她深度对话的母亲。",
        "topics": ["心里难受却只能说出我很烦而无法描述具体情绪", "母亲要求沟通内心感受时感到脑海一片空白"]
    },
    {
        "personality": "敏感多疑与人际被害倾向",
        "description": "总觉得身边的同学或室友在背后排挤自己、说自己坏话，别人低声笑一下就觉得是在嘲笑自己。常用写日记诉说委屈。关系网中有个经常赞美和开导她的挚友小梅。",
        "topics": ["怀疑身边的同学都在背后故意排挤和说自己坏话", "别人低声说话时坚信他们是在密谋针对自己"]
    },
    {
        "personality": "情绪失控与无端哭泣型",
        "description": "情绪阈值极低，经常毫无预兆地在图书馆或教室崩溃流泪，无法自控，自己也觉得丢脸和烦躁。常用撕纸缓解焦虑。关系网中有关心她生活状况的大学辅导员。",
        "topics": ["在图书馆看书时突然情绪崩溃止不住地流泪", "毫无原因地感到悲伤并想通过撕纸发泄"]
    },
    {
        "personality": "孤独自闭与存在虚无感型",
        "description": "觉得即使身处人群也极其孤独，认为自己被世界遗忘了。经常思考人生的意义并得出一切皆虚无的结论，缺乏活着的动力。常用深夜独自散步放松。关系网中有个偶尔联系的高中同学老张。",
        "topics": ["身处热闹的同学聚会却感到被世界彻底抛弃", "认为人生毫无意义且每天都只是在机械地重复"]
    }
]

PROMPT_TEMPLATE = """你是一个专业的心理学对话数据集生成专家。你的任务是根据给定的【用户性格分类】，生成一个适用于微调心理辅导大模型「小影」的训练样本。

【用户性格及背景】: {description}
【对话主题】: {topic}

生成要求：
1. 【结构化用户画像】：
   - 根据用户性格和主题，首先在心底构思该用户的个人特征，包括：
     - nickname (用户昵称，如“小雨”、“默默”、“匿名同学”等)
     - core_stressors (核心压力源列表，包含1-2项，如“保研后学业同辈压力”、“父母过度期待”)
     - effective_coping_methods (曾经有效的压力应对技巧列表，包含1项，如“操场跑步”、“写日记”、“抱猫咪”)
     - entity_relation_map (关键关系网字典，包含1个重要人物或宠物，如 {{"小明": "要好的大学室友，经常倾听其诉苦"}})
2. 【System Prompt 构建】：
   - 根据构思的画像，拼装出大模型「小影」在对话开始时拥有的系统提示词。格式必须完全如下：
     "你是一个面向高校学生的 AI 心理委员，名字叫「小影」，角色定位是温柔、包容、非批判性的心理专家学姐。你非常善于倾听、温暖安慰同学，同时擅长深度剖析并进行针对性的追问引导。\\n\\n【回复风格约束与专业技巧】\\n- 温暖共情：对用户的痛苦表示同理和无条件接纳，给予温暖安慰（如‘我听到了...’、‘这真的很不容易...’，占比60%）。\\n- 启发式追问与剖析：当同学陷入烦躁、易怒、自责等负面情绪时，善于通过温柔的开放性提问进行剖析式追问，引导其层层剥离表面情绪，觉察底层的压力源和核心认知（占比40%）。避免生硬说教。\\n- 长期记忆融合：根据用户画像，自然得体地在对话中嵌入用户的历史应对技巧或关键人际关系进行针对性引导。\\n\\n【长期记忆与用户画像】\\n- 用户昵称: <此处替换为所设计的nickname>\\n- 核心压力源: <此处替换为所设计的core_stressors，逗号分隔>\\n- 历史有效技巧: <此处替换为所设计的effective_coping_methods，逗号分隔>\\n- 关键关系网: <此处替换为所设计的实体及关系说明，如“小明:要好的大学室友，经常倾听其诉苦”>\\n- 历史会话召回线索: 无"
3. 【多轮对话生成 (conversations)】：
   - 模拟生成一段用户（human）和心理委员小影（gpt）之间的多轮对话，包含 3 回合（human说3次，gpt回复3次）。
   - 用户（human）的语言必须非常口语化、真实，反映出其被给定话题所困扰的情绪。
   - 小影（gpt）的回复必须高度符合 System Prompt 中的风格约束（温柔包容，不批判，高共情，少说教）。
   - 【核心要求】小影必须在多轮对话的某一次回复中，非常自然、得体地引用系统提示词中注入的画像信息（例如：主动提到用户的应对方式“要不要再去操场跑跑步释放一下？”，或提及关系网中的关键人“小明最近有陪在你身边吗？”），以体现小影结合长期记忆的特征。
   - 对话总长度控制在 500 字以内，确保整条样本（System + conversations）在 1024 Tokens 以内。

4. 【输出格式】：
   - 你必须返回一个标准的 JSON 对象，不要包裹任何 Markdown 标记（如 ```json），直接输出合法的 JSON，格式如下：
   {{
     "system": "<拼装好的 System Prompt>",
     "conversations": [
       {{"from": "human", "value": "用户的第1次输入"}},
       {{"from": "gpt", "value": "小影的第1次温暖回复"}},
       {{"from": "human", "value": "用户的第2次输入"}},
       {{"from": "gpt", "value": "小影的第2次温暖回复，自然结合长期记忆"}},
       {{"from": "human", "value": "用户的第3次输入"}},
       {{"from": "gpt", "value": "小影的第3次收尾与引导性提问"}}
     ]
   }}
"""

def generate_samples(num_samples_per_topic=4):
    if not API_KEY:
        print("错误: 未找到 SILICONFLOW_API_KEY，请检查 .env 文件。")
        return

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    dataset = []

    # 尝试断点续填/增量保存
    output_file = os.path.join(os.path.dirname(__file__), "mindecho_chat.json")
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                dataset = json.load(f)
                print(f"检测到已存在的数据集文件，已读取 {len(dataset)} 条现有数据以进行增量写入。")
        except Exception as e:
            print(f"加载旧文件失败: {e}，将创建新文件。")
            dataset = []

    print(f"开始使用模型 {GENERATION_MODEL} 生成聊天微调数据集 (ShareGPT 格式)...")
    print(f"当前共配置 {len(SEEDS)} 种性格种子。每个主题将生成 {num_samples_per_topic} 条样本。")

    for seed_idx, seed in enumerate(SEEDS):
        personality = seed["personality"]
        description = seed["description"]
        for topic in seed["topics"]:
            for i in range(num_samples_per_topic):
                # 检查此条目是否需要重新生成（可选：在这里我们直接追加，因为每次有随机化，生成多条也是合理的）
                print(f"[{seed_idx + 1}/{len(SEEDS)}] 正在生成: 【{personality}】 - 【{topic}】 (样本 {i+1}/{num_samples_per_topic})...")
                
                prompt = PROMPT_TEMPLATE.format(
                    description=description,
                    topic=topic
                )

                try:
                    response = client.chat.completions.create(
                        model=GENERATION_MODEL,
                        messages=[
                            {"role": "system", "content": "You are a helpful and precise assistant that outputs valid JSON only. Important: escape any double quotes inside JSON string values using \\\" (e.g., \\\"万一毕不了业\\\")."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.8,
                        response_format={"type": "json_object"},  # 开启 JSON Mode，强制模型输出标准 JSON
                        max_tokens=1500
                    )
                    
                    raw_content = response.choices[0].message.content.strip()
                    
                    # 鲁棒剥离 markdown 块标记
                    if raw_content.startswith("```"):
                        lines = raw_content.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].strip() == "```":
                            lines = lines[:-1]
                        raw_content = "\n".join(lines).strip()

                    # 尝试解析 JSON 并进行兜底修复
                    try:
                        sample_data = json.loads(raw_content)
                    except Exception as json_err:
                        # 兜底修复：去除尾部多余逗号等常见格式错误
                        import re
                        repaired = re.sub(r',\s*([\]}])', r'\1', raw_content)
                        # 替换未转义的双引号（排除 JSON 键值对中的结构双引号，较复杂，先做最基本的逗号修复）
                        sample_data = json.loads(repaired)
                    
                    # 确保符合 LLaMA-Factory ShareGPT 格式
                    if "system" in sample_data and "conversations" in sample_data:
                        dataset.append(sample_data)
                        print("-> 生成并解析成功！正在执行渐进式（异步）保存...")
                        # 每次成功生成一条立刻保存至磁盘，防止断电/报错丢失
                        with open(output_file, "w", encoding="utf-8") as f:
                            json.dump(dataset, f, ensure_ascii=False, indent=2)
                    else:
                        print("-> 生成格式有误，缺少必要字段，跳过。")
                        
                except Exception as e:
                    print(f"-> 请求或解析失败: {e}")
                
                # 短暂休眠，防止触发 rate limit 限制
                time.sleep(1)

    print(f"\n全部生成完毕！最终共收集了 {len(dataset)} 条多轮对话微调样本，已保存至: {output_file}")

if __name__ == "__main__":
    # 每个性格有 2 个 topic，每个 topic 生成 2 条，则每个性格生成 4 条。
    # 总数据量：24 种性格 * 2 个 topic * 2 样本 = 96 条微调数据。
    generate_samples(num_samples_per_topic=4)
