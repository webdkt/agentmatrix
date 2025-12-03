import uvicorn
if __name__ == "__main__":
    print("启动 AgentMailOS...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)