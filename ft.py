
from crewai import Agent, Task, Crew
from crewai.llm import LLM

llm = LLM(
    model="ollama/mistral",  # This name can be anything; just for internal reference
    api_base="http://localhost:11434",
    api_key="ollama",  # Placeholder; Ollama doesn’t require this but LiteLLM expects a non-empty value
    model_name="mistral",  # The actual model name running on Ollama
    temperature=0.7,
    max_tokens=1000,
)

agent = Agent(
    role="Tester",
    goal="Just test if Mistral works",
    backstory="You are a basic test agent.",
    verbose=True,
    llm=llm,
    llm_config={
        "provider": "ollama",
        "config": {
            "model": "mistral",
            "base_url": "http://localhost:11434",
            "temperature": 0.3
        }
    }
)

task = Task(
    description="Say hello and describe your purpose.",
    expected_output="A simple hello and description.",
    agent=agent
)

crew = Crew(agents=[agent], tasks=[task], verbose=True)
output = crew.kickoff()
print(output)
