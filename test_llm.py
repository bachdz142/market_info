from dotenv import load_dotenv

load_dotenv()

from agent.graph import _build_model


def main() -> None:
    model = _build_model()
    response = model.invoke("Reply with exactly one word: 'pong'.")
    print(response.content)


if __name__ == "__main__":
    main()
