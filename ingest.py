"""Optional CLI: (re)build the Chroma index from Zombie_Plan.pdf."""
import rag

if __name__ == "__main__":
    col = rag.get_collection()
    print(f"Existing chunks: {col.count()}")
    rag.ensure_index()
    print(f"Index ready: {rag.get_collection().count()} chunks.")
