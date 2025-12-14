# 伪代码
from core.action import register_action
from datetime import datetime,timezone
import json
import os
import uuid
import asyncio
import textwrap
import traceback
class NotebookMixin:



    @register_action(
        "记笔记。将关键信息归档。",
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

        # 2. (后台自动) 将笔记内容存入向量库    
        await asyncio.to_thread(
            self.add_note,
            content = content,
            record_id = record_id,
            current_timestamp = current_timestamp,
            user_session_id = self.current_user_session_id
        )
        return "Note saved."

        
    def add_note(self, content, record_id, current_timestamp, user_session_id):
        try:
            self.notebook_collection.add(
                documents=[content],
                metadatas=[{
                    "user_session_id": user_session_id,
                    "creator": self.name,
                    "created_at": current_timestamp
                }],
                ids=[record_id]
            )
        except Exception as e:
            traceback.print_exc()
            #print trace in asyncio

    def search_notes(self, query, user_session_id):
        try:
            results = self.notebook_collection.query(
                query_texts=[query],
                where={
                    "$and": [
                        {"user_session_id": user_session_id},
                        {"creator": self.name}
                    ]
                }
            )
            
            if results['documents'] and results['documents'][0]:
                return_str = "Found following notes:\n"
                for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
                    return_str += textwrap.dedent(f"""#### On : {metadata['created_at']}  
                        {doc}

                    """)
                return return_str
            else:
                return "No notes found."
        except Exception as e:
            traceback.print_exc()
            return f"Error searching notes: {str(e)}"
    

    @register_action(
        "查笔记。搜索记忆库。",
        param_infos={
            "query": "想找什么？(自然语言描述)",
        }
    )
    async def search_notebook(self, query):
        result = await asyncio.to_thread(
            self.search_notes,
            query=query,
            user_session_id = self.current_user_session_id
            
        )
        return result
        
        