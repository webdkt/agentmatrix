# AgentMatrix World - Agent Configuration

This directory contains all agent configurations for your Matrix World.

## 📁 Directory Structure

```
agents/
├── README.md              # This file - configuration guide
├── User.yml               # Required: User agent configuration
└── prompts/               # Agent system prompt templates
    └── base.txt          # Base prompt template used by all agents
```

## 📝 Files

### User.yml
The **User agent** represents you (the human user) in the Matrix World.

**Purpose:**
- Acts as your proxy to communicate with other agents
- Receives emails sent by other agents
- Can be configured with various skills (e.g., file system operations)

**Configuration:**
```yaml
name: User
description: Master of world
module: agentmatrix.agents.user_proxy
class_name: UserProxyAgent

mixins:
  - skills.filesystem.FileSkillMixin  # Enables file operations

backend_model: default_llm             # Which LLM to use
```

**⚠️ DO NOT DELETE** - Every Matrix World must have a User agent.

---

### prompts/base.txt

The **base system prompt template** that provides the core instruction framework for all agents.

**Purpose:**
- Defines how agents should behave and think
- Supports Jinja2 template variables (e.g., `{{ name }}`, `{{ description }}`)
- Automatically loaded by AgentLoader during agent initialization

**Template Variables:**
- `{{ name }}` - Agent's name
- `{{ description }}` - Agent's description
- `{{ capabilities }}` - Agent's available skills/tools
- `{{ yellow_page }}` - List of other agents this agent can collaborate with

**Customization:**
You can modify this file to adjust the default behavior and thinking process of all agents in your World.

---

## 🤖 Adding More Agents

To add a new agent to your Matrix World:

1. **Create a new YAML file** in this `agents/` directory
   ```bash
   nano agents/MyAgent.yml
   ```

2. **Basic agent template:**
   ```yaml
   name: MyAgent
   description: A helpful assistant
   module: agentmatrix.agents.based_agent
   class_name: BaseAgent

   mixins:
     - skills.filesystem.FileSkillMixin

   instruction_to_caller: "Be concise and helpful"
   system_prompt: "You are a specialist in..."
   backend_model: default_llm
   ```

3. **Restart the server** to load the new agent:
   ```bash
   python server.py --matrix-world ./YourWorld
   ```

---

## 🔧 Configuration Options

### Available Mixins (Skills)
- `skills.filesystem.FileSkillMixin` - File read/write operations
- `skills.browser.BrowserSkillMixin` - Web browsing capabilities
- More to come...

### Backend Models
- `default_llm` - Your primary LLM (configured in `llm_config.json`)
- `default_slm` - Your smaller/faster LLM for simple tasks

---

## 📚 Next Steps

1. **Configure your LLM** through the web UI (first-time setup)
2. **Customize agent behaviors** by editing YAML files
3. **Create more agents** to build your team
4. **Start collaborating** with your AI agents!

---

## 💡 Tips

- **Keep it simple**: Start with the User agent, add more as needed
- **Test incrementally**: Add one agent at a time and test
- **Read agent logs**: Check `workspace/.matrix/logs/` for agent activity
- **Backup your World**: The entire World directory is self-contained

---

## 🆘 Need Help?

- Check the [AgentMatrix Documentation](https://github.com/webdkt/agentmatrix)
- Review example agents in the project repository
- Open an issue on GitHub for bugs or questions
