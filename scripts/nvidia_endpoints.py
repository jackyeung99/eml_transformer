from sentence_transformers import SentenceTransformer

model = SentenceTransformer("nvidia/llama-nemotron-embed-vl-1b-v2", trust_remote_code=True)

query = "How is AI improving the intelligence and capabilities of robots?"
documents = [
    "AI enables robots to perceive, plan, and act autonomously.",
    "AI is transforming autonomous vehicles by enabling safer, smarter, and more reliable decision-making on the road.",
    "A biological foundation model designed to analyze and generate DNA, RNA, and protein sequences.",
]

# Text-only encoding
query_embeddings = model.encode_query([query])
document_embeddings = model.encode_document(documents)
print(query_embeddings.shape, document_embeddings.shape)
# (1, 2048) (3, 2048)

similarities = model.similarity(query_embeddings, document_embeddings)
print(similarities)
# tensor([[0.4142, 0.4046, 0.0421]])
