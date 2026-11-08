"""Modelos Pydantic de pedido e resposta.

Camada de schema (seção 6.2 do SDD): a parte do controlador que descreve o corpo HTTP. Os
controladores de `app.controllers` validam os pedidos e montam as respostas com estes modelos,
e `app.core.errors` e o middleware montam o envelope de erro com `ErrorResponse`. Os modelos
não conhecem banco nem prompt. O FastAPI gera o OpenAPI a partir deles, e o frontend gera os
tipos a partir do OpenAPI (seção 6.6): mudar um campo muda o contrato. O endpoint de cada
modelo está na seção 12 do SDD.

Os comentários das classes ficam em `#`, e não em docstring. A docstring de um modelo Pydantic
vira a `description` dele no OpenAPI e nos tipos do frontend, e a CI falha quando o contrato
muda sem os arquivos gerados de novo (NFR-16). As poucas docstrings de classe que existem já
estão no contrato; mudar uma delas pede gerar o OpenAPI e os tipos de novo.
"""
