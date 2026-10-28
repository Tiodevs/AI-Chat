# workflows

GitHub Actions. O `ci.yml` roda a API contra `pgvector/pgvector:pg18` e o frontend sem banco. O `evals.yml` sincroniza `evals/public_qa.jsonl` e comenta o resultado na pull request. O `deploy.yml` entra numa etapa seguinte. Seção 22.3 do SDD.
