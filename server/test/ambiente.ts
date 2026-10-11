// Ambiente isolado para os testes: banco em memória, sem agendador, credenciais falsas.
process.env.CAMINHO_BANCO = ':memory:';
process.env.AGENDADOR_DESLIGADO = '1';
process.env.IA_SIMULADA = process.env.IA_SIMULADA ?? '1';
process.env.SMTP_HOST = 'smtp.teste.invalid';
process.env.SMTP_USUARIO = 'comercial@escritorio.invalid';
process.env.SMTP_SENHA = 'x';
process.env.RESPONSAVEL_NOME = 'Fábio';
