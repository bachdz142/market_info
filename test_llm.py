from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage

from agent.llm_fallback import build_structuring_model


def main() -> None:
    model = build_structuring_model()
    response = model.invoke(
        [HumanMessage(content="Reply with an empty signals list — nothing to extract here.")]
    )
    print("provider:", response.get("_provider"), "/", response.get("_model"))
    print(response.get("parsed"))


if __name__ == "__main__":
    main()
