from dotenv import load_dotenv

load_dotenv()

from langchain_tavily import TavilySearch


def main() -> None:
    tool = TavilySearch(max_results=3)
    results = tool.invoke({"query": "test query: latest SBV Vietnam interest rate news"})
    print(results)


if __name__ == "__main__":
    main()
