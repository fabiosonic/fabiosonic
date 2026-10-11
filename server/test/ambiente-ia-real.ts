// Desliga a IA simulada e define chaves falsas para testar o rodízio real com fetch simulado.
process.env.IA_SIMULADA = '0';
process.env.GROQ_API_KEY = 'chave-groq';
process.env.GEMINI_API_KEY = 'chave-gemini';
process.env.GITHUB_MODELS_TOKEN = 'chave-github';
