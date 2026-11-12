# Landing page do Atrium

A página que apresenta o projeto para quem chega de fora: o que o Atrium faz, como ele responde, como é por dentro e que o código é aberto. É um arquivo só, sem build.

| Arquivo | Papel |
|---|---|
| [`index.html`](index.html) | A página inteira: marcação, estilos e o script das animações |

As imagens vêm de [`../assets/screenshots/`](../assets/screenshots/), as mesmas do `README.md` da raiz.

## Como abrir

Os scripts não rodam em `file://` em todo navegador. Sirva a pasta `docs` e abra a página:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory docs
```

Depois abra `http://127.0.0.1:8765/landing/`. Para publicar, o GitHub Pages servindo a pasta `docs` da `main` entrega a página em `/landing/`, sem nenhum passo a mais.

## Identidade e movimento

- **Cores e fontes.** Os tokens da [seção 14.2 do SDD](../sdd/experiencia.md), copiados no `:root` da página: neutros, tema escuro e cor só com significado (os desfechos). Geist e Geist Mono vêm do Google Fonts.
- **Movimento.** GSAP 3.13 e ScrollTrigger, pelo cdnjs. As durações, as curvas e o stagger são os da seção 16.2, os mesmos de [`apps/web/src/motion/tokens.ts`](../../apps/web/src/motion/tokens.ts). Só `transform` e `opacity` são animados.
- **Sem animação.** Com `prefers-reduced-motion` ou sem o GSAP (CDN fora do ar), a página fica estática e completa: nenhum conteúdo depende do script para aparecer.

## O que atualizar quando o projeto mudar

| Mudou | Onde na página |
|---|---|
| Uma resposta fixa em `apps/api/app/prompts/qa.py` ou um rótulo em `apps/web/src/i18n/pt.ts` | A lista `scenarios` no script e as citações da seção "Como responde" |
| O pipeline de perguntas ([guia, parte 4](../guia/04-pergunta-de-ponta-a-ponta.md)) | Os seis passos da seção "Por dentro" |
| As contagens de [engenharia/README.md](../engenharia/README.md#qualidade-em-números) | Os `data-count` da seção de números e a data embaixo |
| A stack | A faixa e a tabela da seção "Stack" |
| Uma captura de tela | Os botões da seção "Telas" (`data-src` e `data-alt`) |
| O endereço do repositório ou da demonstração | Os links `github.com/Tiodevs/AI-Chat` e `atrium-gold.vercel.app` |
