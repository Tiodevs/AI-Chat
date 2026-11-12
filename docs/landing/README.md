# Landing page do Atrium

A página que apresenta o projeto para quem chega de fora: o que o Atrium faz, os compromissos, as telas, que o código é aberto, a documentação e a stack. É um arquivo só, sem build.

| Arquivo | Papel |
|---|---|
| [`index.html`](index.html) | A página inteira: marcação, estilos e o script das animações |
| [`../assets/logo/atrium-mark.svg`](../assets/logo/atrium-mark.svg) | O símbolo da marca, em preto, para usar fora da página |

As imagens vêm de [`../assets/screenshots/`](../assets/screenshots/), as mesmas do `README.md` da raiz.

## Como abrir

Os scripts não rodam em `file://` em todo navegador. Sirva a pasta `docs` e abra a página:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory docs
```

Depois abra `http://127.0.0.1:8765/landing/`. Para publicar, o GitHub Pages servindo a pasta `docs` da `main` entrega a página em `/landing/`, sem nenhum passo a mais.

## Identidade e movimento

- **Marca.** O símbolo é o quadrado do produto transformado na planta de um átrio: a claraboia em cima e a porta embaixo, que juntas se leem como A. Na página ele é o `<symbol id="mark">`, usado na barra do topo e no favicon. O produto, em `apps/web`, ainda usa o quadrado com a letra.
- **Cores e fontes.** A paleta é a do tema escuro do portfólio `felipe-santos` (`src/app/globals.css` de lá): tinta azulada no fundo (`#0f1419`), branco suave no texto (`#dde3e6`) e ciano na marca (`#34c3dd`), que aqui é o `--accent`. As fontes são Geist e Geist Mono, como o produto, mais a Instrument Serif em itálico nas palavras de ênfase dos títulos. Para trocar a cor da página inteira, mude `--accent`.
- **Movimento.** GSAP 3.13 com ScrollTrigger e SplitText, pelo cdnjs. O objeto `motion` do script repete os tokens da seção 16.2, os mesmos de [`apps/web/src/motion/tokens.ts`](../../apps/web/src/motion/tokens.ts), e acrescenta o grupo `display`, só desta página, para os movimentos largos: títulos que sobem por linha, a declaração que acende, as faixas e a marca do fecho. Só `transform` e `opacity` são animados.
- **Telas.** Em tela larga, a lista rola e a moldura ao lado fica parada, mostrando a tela do item que está no meio da janela. Em tela estreita, com `prefers-reduced-motion` ou sem o GSAP, cada item mostra a própria imagem.
- **Sem animação.** Com `prefers-reduced-motion` ou sem o GSAP (CDN fora do ar), a página fica estática e completa: nenhum conteúdo depende do script para aparecer.

## O que atualizar quando o projeto mudar

| Mudou | Onde na página |
|---|---|
| Uma captura de tela | O print da capa (`admin-visao-geral.png`) e os itens da seção "Telas" (`src` e `alt` de cada `tour-img`) |
| A stack | As duas faixas e a lista da seção "Stack" |
| Um documento de entrada (SDD, guia, engenharia, plano) | As linhas da seção "Documentação" |
| Como rodar localmente | O terminal da seção "Código aberto" |
| O endereço do repositório ou da demonstração | Os links `github.com/Tiodevs/AI-Chat` e `atrium-gold.vercel.app` |
