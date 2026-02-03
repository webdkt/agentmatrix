
from ..core.action import register_action
from datetime import datetime,timezone
import json
import os
import uuid
import asyncio
import textwrap
import traceback
class NotebookMixin:

    @register_action(
        "从详细的系统日志记录中查找信息，补充遗忘的记忆",
        param_infos={
            "query": "想找什么？(自然语言描述)"
        }
    )
    async def search_in_diary(self, query):
        max_count = 10 #最多检查 10 封邮件
        session = self.current_session
        user_session_id = session["user_session_id"]
        partial_results = []
        for index in range(max_count):
            mails = self.post_office.get_mails_by_range(user_session_id, self.name, start=index, end=index +1)
            if mails:
                m = mails[0]
                mail_text = str(m)


                search_history_prompt = textwrap.dedent(f"""
                    你是一个专业的历史邮件管理助理。负责从系统邮件历史中查找能够回答用户问题的邮件。
                    你只是负责查找，不需要回答问题。如果发现可以完整回答用户问题的邮件，就报告找到了。
                    如果具有部分有用信息，就摘录出来。
                    如果没有能回答问题的信息，就报告没有找到。

                    用户现在想找的信息是：
                    {query}

                    [现在的查看的邮件是]：
                    {mail_text}

                    [应答的要求]：
                    1. 严格按照下面的专业格式报告查找的结果：
                    2. 如果这封邮件包含用户想找的信息，就输出 "FOUND"。单一单词，不要附加任何额外信息。
                    3. 如果这封邮件包含用户想找的部分信息，就摘录这部分可能有用的信息的原文，并且直接输出。只输出原文，不要任何其他信息。
                    4. 如果这封邮件没有任何有用信息，输出 "NOT_FOUND"。单一单词，不要附加任何额外信息
                    5. 总之，你的输出要么是 "FOUND"，要么是 "NOT_FOUND"，要么是邮件中摘录的部分原文。任何其他内容都被认为是不专业的。
                """)
                messages= [{"role": "user", "content": search_history_prompt}]

                response = await self.cerebellum.backend.think(messages=messages)
                reply_str= response['reply']
                if reply_str == "FOUND":
                    return textwrap.dedent(f"""
                        Found relevant information in email
                        {mail_text}
                    """)
                elif reply_str == "NOT_FOUND":
                    continue
                else:
                    # 部分有用信息

                    partial_results.append(textwrap.dedent(f"""[{m.timestamp}]:
                        {reply_str}
                    """))
        if partial_results:
            return_str = "Found following partial information in diary:\n"
            for info in partial_results:
                return_str += info + "\n"
            return return_str
        else:
            return "No relevant information found in diary."
        


    @register_action(
        "记笔记。记录关键信息",
        param_infos={
            "content": "具体的记忆内容 (自然语言)"
        }
    )
    async def take_note(self, content):
        notebook_filepath = os.path.join(self.workspace_root, ".matrix", self.name, "notebook", f"{self.current_user_session_id}.jsonl")
        if not os.path.exists(notebook_filepath):
            os.makedirs(os.path.dirname(notebook_filepath), exist_ok=True)
        current_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        record_id = str(uuid.uuid4())
        

        note_record ={
            "id":record_id,
            "created_at": current_timestamp,  #用于判断信息的新旧
            "content": content,

        }

        #把笔记保存到文件
        with open(notebook_filepath, "a") as f:
            f.write(json.dumps(note_record) + "\n")
        session = self.current_session
        user_session_id = session["user_session_id"]

        await self.vector_db.add_documents("notebook", [content], 
            metadatas={"created_at": current_timestamp,
                       "creator": self.name,
                       "user_session_id": user_session_id
                }, 
            ids=[record_id]
        )

        
        return "Note saved."

        
    

    
    

    @register_action(
        "Vector Search查笔记。查找以前记录的笔记",
        param_infos={
            "query": "想找什么？(自然语言描述)",
        }
    )
    async def search_notebook(self, query):
        session = self.current_session
        user_session_id = session["user_session_id"]
        where = {
                    "$and": [
                        {"user_session_id": user_session_id},
                        {"creator": self.name}
                    ]
                }
        results = await self.vector_db.query("notebook", [query], where, n_results=5)
        if results['documents'] and results['documents'][0]:
            return_str = "Most relevant notes:\n"
            for doc, metadata,distance in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
                return_str += textwrap.dedent(f"""#### On : {metadata['created_at']} (Vector search distance: {distance} )  
                    
                    {doc}

                """)
            return return_str
        else:
            return "No notes found."



        
        