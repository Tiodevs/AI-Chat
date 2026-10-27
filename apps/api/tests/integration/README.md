# integration

Testes de integração da API contra PostgreSQL com pgvector. Eles migram o banco, inserem linhas e removem a extensão `vector`, então só rodam com `DATABASE_URL` em localhost. Uma URL remota é ignorada. A CI aponta para o contêiner. Seção 21.1 do SDD.
