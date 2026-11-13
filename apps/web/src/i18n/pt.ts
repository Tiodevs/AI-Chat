/**
 * Todos os textos que a pessoa vê, em português do Brasil (seção 15.7).
 *
 * Um objeto só, `pt`, agrupado por tela ou componente. Como o objeto é
 * tipado, uma chave que não existe falha no `tsc`; o `as const` do fim
 * deixa cada texto somente leitura e com o tipo literal. Os textos com
 * `{nome}`, como `{minutes}` e `{count}`, são modelos: o código troca a
 * marca pelo valor com `replace`.
 *
 * Quem usa: as telas e os hooks de `features`, os componentes de
 * `components`, a casca e as rotas de `app`, e os testes, que acham os
 * elementos pelo mesmo texto. As respostas fixas da IA e as falas do
 * cadastro vêm da API, de `apps/api/app/prompts`.
 */
export const pt = {
  // Textos soltos. `appName` vai no título da aba (`PageHeading`) e no
  // logotipo; `skipToContent`, no link da casca; `close`, no botão de
  // fechar de `Dialog` e `Sheet`; `loading`, no carregamento do roteador,
  // das tabelas e do `Spinner`; `couldNotContinue`, no título de erro da
  // moldura e na mensagem genérica dos hooks. `pageNotFound` ainda não tem
  // tela: a Etapa 14.1 cria a página não encontrada.
  appName: "Atrium",
  skipToContent: "Pular para o conteúdo",
  close: "Fechar",
  loading: "Carregando",
  couldNotContinue: "Não foi possível continuar.",
  pageNotFound: "Não encontramos essa página.",
  // Títulos de página: o `h1` de cada tela e o título da aba
  // (`PageHeading`). Os testes da casca e da e2e acham as páginas por eles.
  pages: {
    home: "Início",
    ask: "Conversa",
    register: "Cadastro",
    registerForm: "Cadastro por formulário",
    signIn: "Entrar",
    account: "Conta",
    privacy: "Privacidade",
    terms: "Termos de Uso",
    legalAccept: "Novo aceite",
    admin: "Visão geral",
    documents: "Documentos",
    quality: "Qualidade",
    privacyRequests: "Pedidos de titular",
    attendance: "Fila e atendimentos",
    attendanceCommitment: "Compromisso de confidencialidade",
    adminAttendance: "Atendimentos encerrados",
  },
  // Navegação (seção 15.4): grupos e itens da barra lateral e da busca ⌘K
  // (`app/navigation.ts`), as ações do `GuestHeader`, os links Conta e
  // Entrar do `ProfileButton` e os links de cadastro e entrada do início.
  nav: {
    assistant: "Assistente",
    account: "Conta",
    operations: "Operação",
    system: "Sistema",
    newQuestion: "Nova pergunta",
    conversations: "Conversas",
    register: "Cadastrar com IA",
    registerForm: "Criar conta",
    registerWithAi: "Cadastrar com IA",
    signIn: "Entrar",
    accountPage: "Conta",
    privacy: "Privacidade",
    terms: "Termos de Uso",
    legalAccept: "Novo aceite",
    overview: "Visão geral",
    documents: "Documentos",
    quality: "Qualidade",
    privacyRequests: "Pedidos de privacidade",
    attendanceGroup: "Atendimento",
    attendanceQueue: "Fila e atendimentos",
    attendanceClosed: "Atendimentos encerrados",
  },
  // A barra lateral (`AppSidebar` e `sidebar-body.tsx`), o menu do
  // visitante (`GuestHeader`) e a busca (`SearchDialog`).
  sidebar: {
    label: "Navegação",
    collapse: "Recolher barra lateral",
    expand: "Expandir barra lateral",
    openMenu: "Abrir menu",
    guestMenu: "Acessar",
    search: "Buscar",
    searchDescription: "Ir para uma página do Atrium.",
    searchPlaceholder: "Buscar uma página",
    searchEmpty: "Nenhuma página encontrada.",
  },
  // O card de novidades da barra lateral (`SidebarNoticeCard`).
  notice: {
    title: "Novidades",
    body: "As respostas usam só as informações publicadas do Harborlight. Elas não substituem um atendimento.",
  },
  // O `ProfileButton` do rodapé da barra lateral: o menu com Sair e a
  // preferência de movimento. A aba Perfil da conta repete os rótulos de
  // movimento, e `useSignOut` usa a falha de saída.
  profile: {
    menu: "Menu da conta",
    menuLabel: "{name}, menu da conta",
    guest: "Visitante",
    signOut: "Sair",
    signingOut: "Saindo…",
    signOutFailed: "Não foi possível sair. Tente de novo.",
    motion: "Movimento",
    motionSystem: "Sistema",
    motionReduce: "Reduzir movimento",
    motionAllow: "Animar",
  },
  // Entrar, `/sign-in`: o `SignInForm`, o `useSignIn` e os avisos de
  // limite de tentativas (`features/auth/return-to.ts`).
  signIn: {
    lead: "Use o e-mail e a senha da sua conta.",
    email: "E-mail",
    password: "Senha",
    submit: "Entrar",
    pending: "Entrando…",
    register: "Criar uma conta",
    credentials: "E-mail ou senha incorretos.",
    limitedOne: "Você fez muitas tentativas. Tente de novo em 1 minuto.",
    limitedMany:
      "Você fez muitas tentativas. Tente de novo em {minutes} minutos.",
    emailRequired: "Informe o e-mail.",
    emailInvalid: "Informe um e-mail válido.",
    passwordRequired: "Informe a senha.",
  },
  // A página 403 do `ErrorBoundary` de `app/route-frame.tsx`.
  forbidden: {
    title: "Acesso negado",
    body: "Sua conta não pode abrir esta página.",
    home: "Voltar ao início",
  },
  // O `RequestIdCopy`, que copia o `request_id` nas telas de erro.
  requestId: {
    label: "Identificador do pedido",
    copy: "Copiar identificador",
    copied: "Identificador copiado",
  },
  // A frase genérica do `ErrorBoundary` de `app/route-frame.tsx`.
  error: {
    body: "Tente de novo em alguns instantes.",
  },
  // O título do início, `/` (`HomeScreen`).
  home: {
    title: "Como podemos ajudar no Harborlight?",
  },
  // O `SafetyNotice` permanente sobre IA e orientação médica (seção 15.6).
  safety: {
    title: "O Atrium é uma inteligência artificial",
    body: "As respostas vêm das informações publicadas do Harborlight General Hospital. Elas não substituem um atendimento e não são orientação médica.",
  },
  // Início e conversa, `/` e `/ask/:id?`: o `Composer`, as mensagens
  // (`UserMessage`, `AssistantMessage`, `ChatThread`), as fontes
  // (`CitationChip`, `SourceList`) e os estados da seção 15.5. Os textos de
  // erro e de limite saem de `useAskConversation` e de
  // `features/ask/model.ts`.
  ask: {
    suggestionsLabel: "Sugestões",
    questionLabel: "Sua pergunta",
    placeholder: "Pergunte sobre visita, caminhos ou horários",
    send: "Enviar",
    sending: "Enviando",
    stop: "Parar",
    healthHint:
      "Não envie sintomas nem nomes de medicamentos. O Atrium não dá orientação médica.",
    useful: "Útil",
    notUseful: "Não útil",
    copy: "Copiar resposta",
    copied: "Resposta copiada",
    retry: "Tentar de novo",
    interrupted: "Interrompida.",
    privacyNote: "Para proteger sua privacidade, não guardamos esta mensagem.",
    replacedNote: "Não consegui confirmar essa resposta, então a substituí.",
    sources: "Fontes",
    showSources: "Mostrar fontes",
    hideSources: "Ocultar fontes",
    waiting: "Preparando a resposta",
    limitedOne: "Você fez muitas perguntas. Tente de novo em 1 minuto.",
    limitedMany:
      "Você fez muitas perguntas. Tente de novo em {minutes} minutos.",
    unavailable:
      "O Atrium está temporariamente indisponível. Você pode ligar para a mesa telefônica no (555) 014-2600.",
    couldNotFinish: "Não foi possível concluir a resposta.",
    alreadyRated: "Esta resposta já foi avaliada.",
    thread: "Mensagens da conversa",
    // O `OutcomeBadge` de cada resposta.
    outcomes: {
      answered: "Respondida",
      abstained: "Não está nas informações publicadas",
      refused: "Orientação médica recusada",
      replaced: "Substituída",
      unavailable: "Indisponível",
    },
    // As quatro sugestões do início, em `suggestion-chips.tsx`.
    suggestions: [
      {
        id: "visiting",
        label: "Horário de visita",
        question: "Qual é o horário de visita?",
      },
      {
        id: "parking",
        label: "Estacionamento",
        question: "Onde posso estacionar?",
      },
      {
        id: "emergency",
        label: "Entrada de emergência",
        question: "Onde fica a entrada de emergência?",
      },
      {
        id: "cafeteria",
        label: "Horário do refeitório",
        question: "Qual é o horário do refeitório?",
      },
    ],
  },
  // Cadastro por conversa (`/register`) e por formulário
  // (`/register/form`): as telas, o `ProfileSummaryCard`, o `PasswordCard`,
  // o `ConsentFieldSet`, o `AssistantBubble` e a validação de
  // `features/registration/model.ts`. A conta reaproveita os tipos de
  // visitante e os motivos, e o novo aceite, os links dos documentos.
  registration: {
    lead: "Crie sua conta conversando. Você vê e corrige cada dado antes de confirmar.",
    formLead:
      "Os mesmos dados e aceites do cadastro por conversa, nesta página.",
    stepsLabel: "Etapas do cadastro",
    // O `RegistrationStepper`, hoje só no Storybook (seção 14.6).
    steps: {
      details: "Dados",
      password: "Senha",
      review: "Revisão",
      agree: "Aceite",
    },
    summaryTitle: "O que entendemos",
    summaryShow: "Ver o que entendemos ({count})",
    summaryHide: "Ocultar o que entendemos",
    summaryEmpty: "Ainda não informado",
    understood: "{field}: {value}",
    why: "Por que pedimos",
    edit: "Editar",
    save: "Salvar",
    cancel: "Cancelar",
    skip: "Pular",
    skipMessage: "Quero pular este campo.",
    optionalHint: "Você pode pular este campo.",
    useForm: "Usar o formulário",
    signIn: "Entrar",
    confirm: "Está certo",
    correct: "Quero corrigir",
    createAccount: "Criar conta",
    creating: "Criando a conta…",
    send: "Enviar",
    sending: "Enviando",
    replyForm: "Enviar uma resposta",
    messageLabel: "Sua resposta",
    messagePlaceholder: "Escreva aqui",
    passwordNote: "Sua senha vai direto para o nosso servidor. A IA não a vê.",
    passwordForm: "Definir a senha",
    passwordHint: "Use de 12 a 72 caracteres.",
    strengthLabel: "Força da senha",
    // O medidor de força do `PasswordCard`.
    strength: {
      empty: "A força da senha aparece aqui.",
      short: "Curta demais",
      long: "Longa demais",
      fair: "Razoável",
      good: "Boa",
      strong: "Forte",
    },
    consentsTitle: "Aceites",
    requiredLegend: "Obrigatórios",
    optionalLegend: "Opcionais",
    terms: "Li e aceito os Termos de Uso e o Aviso de Privacidade.",
    termsLink: "Termos de Uso",
    privacyLink: "Aviso de Privacidade",
    age: "Declaro que tenho 18 anos ou mais.",
    personalization:
      "Personalizar com o tipo de visitante e o motivo da visita.",
    personalizationBadge: "Consentimento destacado",
    personalizationNote:
      "Tipo de visitante e motivo da visita podem indicar que você é paciente. Só guardamos esses dados com este aceite. Ele é opcional e começa desmarcado.",
    quality: "Usar minhas conversas para melhorar o assistente.",
    qualityNote: "Opcional. Você pode desligar isso depois, na conta.",
    sensitiveKept:
      "Só guardamos tipo de visitante e motivo da visita se a personalização estiver aceita.",
    termsRequired: "Aceite os Termos e o Aviso de Privacidade para continuar.",
    ageRequired: "Confirme que você tem 18 anos ou mais para continuar.",
    unavailable:
      "O assistente do cadastro está indisponível agora. Tente de novo em instantes ou use o formulário.",
    unavailableForm:
      "O cadastro por conversa está indisponível. Use o formulário.",
    assistantName: "Assistente do Atrium",
    typing: "O assistente está escrevendo",
    errorTitle: "Não deu para enviar",
    retry: "Tentar de novo",
    dismiss: "Fechar aviso",
    sessionMissing: "Não encontrei este cadastro. Você pode preencher do zero.",
    thread: "Conversa do cadastro",
    // Os nomes dos campos: formulário, `PasswordCard` e mensagens de erro.
    fields: {
      full_name: "Nome completo",
      email: "E-mail",
      phone: "Telefone",
      visitor_type: "Tipo de visitante",
      visit_reason: "Motivo da visita",
      password: "Senha",
    },
    // O "Por que pedimos" de cada campo no `ProfileSummaryCard`.
    reasons: {
      full_name: "O nome identifica a sua conta.",
      email:
        "O e-mail serve para entrar e para receber um aviso sobre a conta.",
      phone:
        "O telefone é opcional. Ele só é usado se você quiser um contato da mesa.",
      visitor_type:
        "Opcional. Ajuda a personalizar respostas públicas. Pode indicar que você é paciente.",
      visit_reason:
        "Opcional. Ajuda a personalizar respostas públicas. Pode indicar que você é paciente.",
    },
    // As opções de tipo de visitante e de motivo da visita: resumo,
    // formulário e aba Perfil da conta.
    visitorTypes: {
      patient: "Paciente",
      visitor: "Visita",
      caregiver: "Cuidador",
    },
    visitReasons: {
      visiting_someone: "Visitar alguém",
      own_appointment: "Minha consulta",
      exam_or_test: "Exame",
      accompanying_someone: "Acompanhar alguém",
      administrative: "Assunto administrativo",
      other: "Outro",
    },
    nameRequired: "O nome é obrigatório.",
    nameInvalid: "O nome precisa ter de 2 a 80 caracteres.",
    emailRequired: "O e-mail é obrigatório.",
    emailInvalid: "Digite um e-mail válido.",
    phoneInvalid:
      "O telefone precisa ter de 7 a 20 caracteres, com dígitos, espaço e + - ( ).",
    passwordRequired: "Defina uma senha para continuar.",
    passwordInvalid: "A senha precisa ter de 12 a 72 caracteres.",
    visitorInvalid: "Escolha paciente, visita ou cuidador.",
    reasonInvalid: "Escolha um motivo da lista.",
    limitedOne: "Você fez muitas tentativas. Tente de novo em 1 minuto.",
    limitedMany:
      "Você fez muitas tentativas. Tente de novo em {minutes} minutos.",
  },
  // Conta, `/account` (`AccountScreen`), com as abas da seção 15.5.
  // `features/account/model.ts` usa a validação e a palavra que confirma a
  // exclusão.
  account: {
    tabsLabel: "Seções da conta",
    loadError: "Não foi possível carregar esta seção.",
    // Os nomes das abas.
    tabs: {
      profile: "Perfil",
      conversations: "Conversas",
      privacy: "Privacidade",
    },
    // A aba Perfil.
    profile: {
      email: "E-mail",
      emailNote: "O e-mail é o seu acesso e não muda por aqui.",
      fullName: "Nome completo",
      phone: "Telefone",
      phoneHint: "Opcional. Deixe em branco para remover.",
      visitorType: "Tipo de visitante",
      visitReason: "Motivo da visita",
      sensitiveOff:
        "Tipo de visitante e motivo da visita só aparecem com a personalização ativa. Ative em Privacidade.",
      save: "Salvar alterações",
      saving: "Salvando…",
      saved: "Alterações salvas.",
      nameRequired: "O nome é obrigatório.",
      nameInvalid: "O nome precisa ter de 2 a 80 caracteres.",
      phoneInvalid:
        "O telefone precisa ter de 7 a 20 caracteres, com dígitos, espaço e + - ( ).",
      motionTitle: "Movimento",
      motionHint: "Controla as animações do Atrium neste navegador.",
    },
    // A aba Conversas.
    conversations: {
      empty: "Nenhuma conversa ainda.",
      untitled: "Conversa sem pergunta",
      listLabel: "Suas conversas",
      loading: "Carregando conversas",
    },
    // A aba Privacidade: consentimentos, exportação e exclusão da conta.
    privacy: {
      consentsTitle: "Seus consentimentos",
      consentsLead:
        "Você pode desligar um consentimento opcional a qualquer momento. Desligar a personalização apaga o tipo de visitante e o motivo da visita.",
      termsRequired: "Termos de Uso e Aviso de Privacidade",
      termsRequiredNote: "Obrigatório para ter uma conta.",
      personalization: "Personalizar respostas com o meu perfil",
      personalizationNote:
        "Tipo de visitante e motivo da visita podem indicar que você é paciente. Opcional.",
      quality: "Usar minhas conversas para melhorar o assistente",
      qualityNote:
        "Opcional. Sem isso, suas conversas não entram na avaliação.",
      grantedOn: "Aceito em {date}",
      off: "Desligado",
      version: "Versão {version}",
      changeFailed: "Não foi possível mudar este consentimento.",
      exportTitle: "Exportar meus dados",
      exportLead:
        "Baixe um arquivo JSON com o seu perfil, consentimentos, conversas, fontes e avaliações.",
      exportButton: "Exportar meus dados",
      exporting: "Preparando…",
      exported: "A exportação foi baixada.",
      deleteTitle: "Excluir minha conta",
      deleteLead:
        "Apaga o seu perfil, os consentimentos e as conversas. Não dá para desfazer.",
      deleteButton: "Excluir minha conta",
      deleteDialogTitle: "Excluir minha conta?",
      deleteDialogBody:
        "Vamos apagar o seu perfil, os consentimentos e todas as suas conversas, e encerrar a sessão. Não dá para desfazer.",
      deleteConfirmLabel: "Digite EXCLUIR para confirmar",
      deleteConfirmWord: "EXCLUIR",
      deleteCancel: "Cancelar",
      deleteConfirm: "Excluir para sempre",
      deleting: "Excluindo…",
      requestsLink: "Fazer um pedido ao encarregado de dados",
    },
  },
  // O Aviso de Privacidade, `/privacy` (`PrivacyScreen`, seção 11.11), em
  // seções com âncoras. Os Termos usam também `fictional`.
  privacyNotice: {
    version: "Versão {version}",
    contentsLabel: "Nesta página",
    fictional:
      "O Harborlight General Hospital e o Atrium são fictícios. Use só dados inventados.",
    sections: {
      controller: {
        title: "Quem cuida dos seus dados",
        body: [
          "O controlador é quem opera esta implantação do Atrium, em nome do Harborlight General Hospital.",
          "A mesma pessoa é o encarregado de dados (art. 41 da LGPD).",
        ],
        contact: "Contato do encarregado: {email}",
        contactMissing:
          "O contato do encarregado ainda não foi configurado. Use o formulário do canal no fim desta página.",
      },
      data: {
        title: "Que dados tratamos e por quê",
        columns: ["Dado", "Finalidade", "Base legal"],
        rows: [
          [
            "Nome, e-mail e senha (guardada como hash)",
            "Ter uma conta e entrar",
            "Execução de contrato",
          ],
          ["Telefone, opcional", "Contato do perfil", "Execução de contrato"],
          [
            "Tipo de visitante e motivo da visita, opcionais",
            "Personalizar respostas públicas",
            "Consentimento específico e destacado",
          ],
          [
            "Conversas de membro",
            "Guardar o histórico que você pediu",
            "Execução de contrato",
          ],
          [
            "Conversas de convidado",
            "Responder à pergunta feita",
            "Pedido do titular",
          ],
          [
            "Conversas usadas para melhoria",
            "Avaliar e melhorar o assistente",
            "Consentimento",
          ],
          [
            "Rastros de IA mascarados",
            "Qualidade e diagnóstico",
            "Legítimo interesse",
          ],
          [
            "HMAC do IP e navegador",
            "Segurança e limite de pedidos",
            "Legítimo interesse",
          ],
          [
            "Registros de consentimento",
            "Provar o seu consentimento",
            "Cumprimento de obrigação",
          ],
        ],
      },
      health: {
        title: "Dados de saúde",
        body: [
          "Não compartilhe dados de saúde. O Atrium não dá orientação médica.",
          "Uma mensagem que pede orientação médica não é guardada. O histórico mostra que ela foi descartada.",
          "O texto da pergunta passa pelo Google, de forma transitória, para ser classificado e respondido.",
        ],
      },
      // O canal WhatsApp (SDD 30.9.4).
      whatsapp: {
        title: "WhatsApp",
        body: [
          "Você pode perguntar ao Atrium pelo WhatsApp do Harborlight. A primeira resposta traz um aviso de que você fala com uma inteligência artificial.",
          "Guardamos o identificador que o WhatsApp dá a você para o hospital e, quando o WhatsApp o envia, o seu número. O identificador é o que usamos para responder. O número fica guardado só como reserva de envio e nunca aparece para a equipe, nos registros nem nos rastros de IA.",
          "Não baixamos fotos, áudios nem documentos. Não envie exames, receitas ou documentos.",
          "O WhatsApp é da Meta, que trata as mensagens nos Estados Unidos para entregá-las. A pergunta segue para o Google, como no site.",
          "A conversa do WhatsApp é apagada 30 dias depois da sua última mensagem. Para apagar antes, envie APAGAR DADOS e confirme. As mensagens no seu aparelho continuam com você.",
          "O Atrium nunca começa uma conversa: ele só responde a quem escreve.",
        ],
      },
      processors: {
        title: "Com quem compartilhamos",
        lead: "Estes operadores tratam dados fora do Brasil, com as cláusulas contratuais de cada provedor (art. 33 da LGPD).",
        columns: ["Operador", "País", "Finalidade"],
        rows: [
          [
            "Railway",
            "Estados Unidos",
            "Hospedagem da API, do banco de dados e da tarefa de retenção",
          ],
          [
            "Vercel",
            "Estados Unidos",
            "Entrega do site e encaminhamento dos pedidos para a API",
          ],
          [
            "Google (API Gemini)",
            "Estados Unidos",
            "Classificar e responder perguntas e entender o cadastro por conversa",
          ],
          [
            "LangChain (LangSmith)",
            "Estados Unidos",
            "Rastros de IA mascarados, para qualidade e diagnóstico",
          ],
          [
            "Meta (WhatsApp)",
            "Estados Unidos",
            "Entregar as mensagens do canal WhatsApp",
          ],
        ],
      },
      retention: {
        title: "Por quanto tempo guardamos",
        columns: ["Dado", "Prazo"],
        rows: [
          [
            "Conta e perfil",
            "Até você excluir a conta, ou 24 meses sem entrar",
          ],
          [
            "Conversas de membro",
            "12 meses depois da última mensagem, ou até a exclusão da conta",
          ],
          ["Conversas de convidado", "30 dias"],
          [
            "Conversas do WhatsApp, identificador e número",
            "30 dias depois da sua última mensagem, ou na hora com APAGAR DADOS",
          ],
          [
            "Sessão de cadastro",
            "Apagada na conclusão, no abandono ou em 24 horas",
          ],
          ["Sessões de entrada", "14 dias depois de expirar ou de você sair"],
          ["Limites de pedidos", "48 horas"],
          ["Registros de consentimento", "Enquanto a conta existir"],
          ["Auditoria", "2 anos, sem e-mail nem conteúdo"],
          ["Pedidos ao encarregado", "2 anos depois de fechados"],
        ],
      },
      rights: {
        title: "Seus direitos",
        body: [
          "Na página da conta você exporta seus dados em JSON, corrige o perfil, desliga consentimentos opcionais e exclui a conta, na hora.",
          "Pelo canal abaixo você pede acesso, correção, eliminação, portabilidade, informação sobre compartilhamento, revogação ou oposição. Respondemos em até 15 dias corridos.",
          "Convidados sem conta usam o canal, porque não conseguimos provar quem é o dono de uma conversa anônima depois que o cookie se perde.",
          "Os consentimentos opcionais são livres. Sem eles você usa o Atrium do mesmo jeito.",
        ],
      },
      cookies: {
        title: "Cookies",
        lead: "Usamos só cookies estritamente necessários. Não há cookie de análise nem de publicidade, por isso não há banner de cookies.",
        columns: ["Cookie", "Para que serve", "Duração"],
        rows: [
          [
            "atrium_session",
            "Manter você conectado à conta",
            "14 dias, ou até você sair",
          ],
          [
            "atrium_guest",
            "Manter a conversa de convidado depois de recarregar a página",
            "30 dias",
          ],
        ],
        storage:
          "A preferência de movimento fica no armazenamento local do navegador e não sai dele.",
      },
      security: {
        title: "Segurança",
        body: [
          "Todo o tráfego usa TLS. Senhas usam argon2id, e tokens de sessão e IPs ficam só como hash.",
          "O admin vê conversas pseudonimizadas. Revelar a identidade exige um motivo, que fica registrado.",
          "O site não carrega scripts nem fontes de terceiros.",
        ],
      },
      incidents: {
        title: "Incidentes",
        body: [
          "Se um incidente puder gerar risco ou dano relevante, avisamos a ANPD e as pessoas afetadas em até 3 dias úteis.",
        ],
      },
      channel: {
        title: "Canal do titular",
        lead: "Envie um pedido ao encarregado. Não é preciso ter conta. Respondemos pelo e-mail informado em até 15 dias corridos.",
      },
    },
  },
  // O formulário do canal do titular, no fim de `/privacy` (seção 11.5). A
  // fila do admin usa `types` para nomear cada pedido.
  privacyRequest: {
    email: "E-mail para a resposta",
    type: "Tipo do pedido",
    description: "Descreva o pedido",
    descriptionHint: "Até 2.000 caracteres. Não inclua dados de saúde.",
    submit: "Enviar pedido",
    submitting: "Enviando…",
    sent: "Pedido enviado. O prazo de resposta é {date}.",
    emailInvalid: "Digite um e-mail válido para a resposta.",
    typeRequired: "Escolha o tipo do pedido.",
    descriptionRequired: "Descreva o pedido.",
    descriptionTooLong: "Descreva o pedido em até 2.000 caracteres.",
    types: {
      access: "Acesso",
      correction: "Correção",
      deletion: "Eliminação",
      portability: "Portabilidade",
      consent_revocation: "Revogar consentimento",
      information_about_sharing: "Compartilhamento",
      objection: "Oposição",
      other: "Outro",
    },
  },
  // Os Termos de Uso, `/terms` (`TermsScreen`). O `id` de cada seção é a
  // âncora dela na página.
  termsOfUse: {
    version: "Versão {version}",
    sections: [
      {
        id: "o-que-e",
        title: "O que é o Atrium",
        body: [
          "O Atrium é o assistente público do Harborlight General Hospital, um hospital fictício na cidade fictícia de Port Meridian. Ele responde perguntas sobre visitas, caminhos, horários e serviços com base nas informações publicadas pelo hospital.",
          "O Atrium é uma inteligência artificial. As respostas trazem as fontes usadas e podem conter erros.",
        ],
      },
      {
        id: "nao-e-orientacao-medica",
        title: "Não é orientação médica",
        body: [
          "O Atrium não dá diagnóstico, não indica tratamento nem medicamento. Numa emergência, ligue para o número local de emergência.",
        ],
      },
      {
        id: "conta",
        title: "Sua conta",
        body: [
          "Para criar uma conta você precisa ter 18 anos ou mais e aceitar estes Termos e o Aviso de Privacidade.",
          "Você cuida da sua senha. Você pode corrigir, exportar ou excluir seus dados na página da conta.",
        ],
      },
      {
        id: "uso-aceitavel",
        title: "Uso aceitável",
        body: [
          "Não tente contornar os limites de pedidos, burlar as proteções do assistente nem usar o Atrium para obter dados de outras pessoas.",
          "Podemos limitar ou suspender um acesso que coloque o serviço ou outras pessoas em risco.",
        ],
      },
      {
        id: "disponibilidade",
        title: "Disponibilidade",
        body: [
          "O Atrium pode ficar indisponível ou mudar sem aviso. Quando o assistente não puder responder, ele mostra o telefone da mesa do hospital.",
        ],
      },
      {
        id: "privacidade",
        title: "Privacidade",
        body: ["O tratamento dos seus dados está no Aviso de Privacidade."],
      },
      {
        id: "mudancas",
        title: "Mudanças nestes Termos",
        body: [
          "Quando estes Termos ou o Aviso mudarem, a versão nova aparece no topo da página e você aceita de novo na próxima entrada.",
        ],
      },
    ],
    privacyLink: "Ler o Aviso de Privacidade",
  },
  // Visão geral do admin, `/admin` (`OverviewScreen`, seção 15.5). A
  // Qualidade reaproveita o período, os desfechos e o feedback.
  insights: {
    period: {
      label: "Período",
      days7: "7 dias",
      days30: "30 dias",
      comparedTo: "contra os {days} dias anteriores",
    },
    loadFailed: "Não foi possível carregar os indicadores.",
    notAvailable: "Sem dados",
    delta: {
      up: "Alta de {value}",
      down: "Queda de {value}",
      flat: "Sem variação",
      none: "Sem período anterior",
    },
    // Os quatro `StatCard`.
    stats: {
      questions: "Perguntas",
      answerRate: "Taxa de respostas",
      abstentionRate: "Taxa de abstenção",
      helpfulRate: "Taxa de útil",
      ariaLabel: "{label}: {value}. {delta}",
    },
    // O `TrendChartCard` e a tabela equivalente para leitores de tela.
    trend: {
      title: "Perguntas ao longo do tempo",
      questions: "Perguntas",
      answered: "Respondidas",
      date: "Data",
      tableCaption: "Perguntas e respostas por dia",
    },
    // O `SegmentedStatusCard` de desfechos, com as abas.
    outcomesCard: {
      title: "Desfechos",
      outcome: "Desfecho",
      intent: "Intenção",
      feedback: "Feedback",
      empty: "Nenhuma resposta no período.",
      share: "{count} ({percent})",
    },
    // Os desfechos gravados (seção 7.1), nos gráficos e nos filtros.
    outcomes: {
      answered: "Respondida",
      abstained: "Fora das informações",
      refused: "Orientação médica recusada",
      off_topic: "Fora do tema",
      grounding_failed: "Substituída por resposta segura",
      cancelled: "Cancelada",
      degraded: "Sem orçamento",
      error: "Erro",
    },
    intents: {
      public_info: "Informação pública",
      medical_advice: "Orientação médica",
      off_topic: "Fora do tema",
    },
    feedback: {
      helpful: "Útil",
      not_helpful: "Não útil",
      none: "Sem feedback",
    },
    // O `GroupedBarCard` do funil de cadastro.
    funnel: {
      title: "Funil de cadastro",
      chat: "Conversa com IA",
      form: "Formulário",
      step: "Etapa",
      steps: {
        started: "Iniciado",
        password_set: "Senha definida",
        completed: "Concluído",
      },
      tableCaption: "Cadastros por etapa, conversa contra formulário",
    },
    // O card do orçamento diário de tokens.
    budget: {
      title: "Orçamento diário de tokens",
      used: "{used} de {budget} tokens hoje",
      unlimited: "Sem orçamento configurado. {used} tokens hoje.",
      nearLimit: "Perto do limite: as respostas param ao chegar em 100%.",
      label: "Uso do orçamento de hoje",
    },
  },
  // Qualidade, `/admin/quality` (`QualityScreen`): filtros, a tabela de
  // conversas, o inspetor em `Sheet` e o diálogo de revelar identidade.
  quality: {
    lead: "Conversas pseudonimizadas para revisar respostas. Só aparecem convidados e membros que consentiram com a melhoria.",
    filters: {
      title: "Filtros",
      outcome: "Desfecho",
      anyOutcome: "Todos os desfechos",
      feedback: "Feedback",
      anyFeedback: "Todos",
    },
    table: {
      caption: "Conversas recentes",
      subject: "Pessoa",
      lastActivity: "Última atividade",
      questions: "Perguntas",
      lastOutcome: "Último desfecho",
      feedback: "Feedback",
      actions: "Ações",
      open: "Abrir conversa",
      empty: "Nenhuma conversa com esses filtros.",
      feedbackCounts: "{helpful} útil · {notHelpful} não útil",
      noFeedback: "Sem feedback",
    },
    subject: {
      guest: "Convidado",
      member: "Membro",
      label: "{kind} {pseudonym}",
    },
    inspector: {
      title: "Conversa {pseudonym}",
      description:
        "Identidade pseudonimizada. Abrir esta conversa ficou registrado na auditoria.",
      loading: "Carregando a conversa",
      user: "Pergunta",
      assistant: "Resposta",
      promptVersion: "Prompt {version}",
      requestId: "request_id",
      latency: "{ms} ms",
      trace: "Ver rastro no LangSmith",
      traceId: "Rastro {id}",
      sources: "Fontes",
      rating: {
        helpful: "Marcada como útil",
        not_helpful: "Marcada como não útil",
      },
      loadFailed: "Não foi possível abrir a conversa.",
    },
    reveal: {
      action: "Revelar identidade",
      title: "Revelar a identidade do membro",
      description:
        "Use só quando houver motivo, como um pedido do titular. O motivo fica gravado na auditoria.",
      reason: "Motivo",
      reasonHint: "De 10 a 500 caracteres.",
      reasonInvalid: "Explique o motivo em 10 a 500 caracteres.",
      confirm: "Revelar",
      confirming: "Revelando…",
      cancel: "Cancelar",
      revealed: "{name} · {email}",
      guestHint: "Conversa de convidado: não há identidade para revelar.",
    },
  },
  // Documentos, `/admin/documents` (`DocumentsScreen`): o envio com o
  // `FileDropzone`, a tabela, os status e as ações de substituir, tentar de
  // novo e arquivar.
  documents: {
    lead: "Envie, substitua e arquive os documentos que o assistente usa para responder.",
    dropzone: {
      label: "Arquivo",
      prompt: "Arraste um arquivo para cá ou escolha no computador",
      choose: "Escolher arquivo",
      hint: "Markdown (.md), texto (.txt) ou PDF, até 10 MB.",
      selected: "Selecionado: {name} ({size})",
      clear: "Remover arquivo",
      tooLarge: "O arquivo passa de 10 MB.",
      wrongType: "Envie um arquivo Markdown (.md), texto (.txt) ou PDF (.pdf).",
      required: "Escolha um arquivo.",
    },
    upload: {
      title: "Enviar documento",
      titleLabel: "Título",
      titleHint: "Opcional. Sem título, usamos o nome do arquivo.",
      submit: "Enviar",
      submitting: "Enviando…",
      sent: "“{title}” foi enviado. A ingestão começou.",
    },
    table: {
      caption: "Documentos do corpus",
      title: "Título",
      activeVersion: "Versão ativa",
      status: "Status",
      updatedAt: "Atualizado em",
      actions: "Ações",
      noActive: "Nenhuma",
      version: "v{version}",
      empty: "Nenhum documento ainda. Envie o primeiro acima.",
      loadFailed: "Não foi possível carregar os documentos.",
    },
    status: {
      processing: "Processando",
      ready: "Pronto",
      failed: "Falhou",
      archived: "Arquivado",
    },
    processingNote:
      "A versão {version} está em processamento. A versão ativa continua respondendo.",
    failedNote: "A versão {version} falhou: {error}",
    actions: {
      replace: "Substituir",
      retry: "Tentar de novo",
      retrying: "Tentando…",
      archive: "Arquivar",
      archiveTitle: "Arquivar “{title}”?",
      archiveBody:
        "O documento sai das respostas do assistente na hora. Ele continua na lista como arquivado.",
      archiveConfirm: "Arquivar documento",
      cancel: "Cancelar",
      archived: "“{title}” foi arquivado.",
      retried: "A ingestão de “{title}” começou de novo.",
    },
    replace: {
      title: "Substituir documento",
      description:
        "Envie a nova versão de “{title}”. A versão ativa continua respondendo até a nova ficar pronta.",
      submit: "Enviar nova versão",
      submitting: "Enviando…",
      sent: "Nova versão de “{title}” enviada. A ingestão começou.",
    },
  },
  // O `DueDateBadge` dos pedidos de titular (seção 14.6).
  dueDate: {
    overdueToday: "Atrasado há menos de 1 dia",
    overdueOne: "Atrasado há 1 dia",
    overdueMany: "Atrasado há {n} dias",
    dueToday: "Vence em menos de 1 dia",
    dueOne: "Vence em 1 dia",
    dueMany: "Vence em {n} dias",
    closed: "Fechado em {date}",
    deadline: "Prazo: {date}",
  },
  // Pedidos de titular, `/admin/privacy` (`PrivacyQueueScreen`): os
  // `StatTile` do resumo, a tabela e o `Sheet` do pedido.
  privacyQueue: {
    lead: "Pedidos abertos pelo canal do titular. O prazo é de 15 dias corridos, e os atrasados aparecem primeiro.",
    summary: {
      label: "Resumo da fila",
      overdue: "Atrasados",
      open: "Abertos",
      inProgress: "Em andamento",
    },
    table: {
      caption: "Pedidos de titular, atrasados primeiro",
      type: "Tipo",
      contact: "Contato",
      receivedAt: "Recebido em",
      deadline: "Prazo",
      status: "Status",
      actions: "Ações",
      open: "Abrir pedido",
      empty: "Nenhum pedido de titular por enquanto.",
      loadFailed: "Não foi possível carregar os pedidos.",
    },
    status: {
      open: "Aberto",
      in_progress: "Em andamento",
      done: "Concluído",
      rejected: "Recusado",
    },
    detail: {
      title: "Pedido de {type}",
      description:
        "Responda ao titular pelo e-mail de contato. Cada mudança de status fica registrada na auditoria.",
      contact: "Contato",
      receivedAt: "Recebido em",
      closedAt: "Fechado em",
      account: "Conta",
      linked: "Enviado com sessão de membro",
      notLinked: "Sem conta vinculada",
      request: "O que a pessoa pediu",
      statusLabel: "Status",
      note: "Nota de resolução",
      noteHint:
        "Até 2.000 caracteres. Obrigatória para concluir ou recusar. Não inclua dados de saúde.",
      noteRequired:
        "Escreva a nota de resolução para concluir ou recusar o pedido.",
      noteKeep: "Em branco, a nota atual continua gravada.",
      save: "Salvar",
      saving: "Salvando…",
      saved: "Pedido atualizado: {status}.",
      closedNotice: "Este pedido foi fechado e não muda mais.",
      noNote: "Sem nota de resolução.",
    },
  },
  // Novo aceite, `/legal/accept` (`LegalAcceptScreen`, seção 13.3).
  legalAccept: {
    lead: "Atualizamos os Termos de Uso e o Aviso de Privacidade (versão {version}). Leia e aceite para continuar.",
    accept: "Aceitar e continuar",
    accepting: "Aceitando…",
    upToDate: "Você já aceitou a versão vigente.",
    continue: "Continuar",
  },
  // Atendimento humano pelo lado do visitante, na conversa `/ask/:id`
  // (seções 29.5, 29.9.5 e 29.11): `HandoffOffer`, `HandoffDialog`,
  // `HandoffStatusBar`, `AttendantMessage` e o bloco do atendimento.
  handoff: {
    offerQuestion: "Quer falar com uma pessoa da equipe?",
    offerButton: "Falar com uma pessoa",
    busy: "A fila está cheia agora. Tente de novo em alguns minutos ou ligue para a mesa telefônica no (555) 014-2600.",
    closed:
      "Ninguém da equipe está disponível agora. Você pode ligar para a mesa telefônica no (555) 014-2600.",
    blocked:
      "O atendimento por uma pessoa não está disponível para você agora. Ligue para a mesa telefônica no (555) 014-2600.",
    // O diálogo de confirmação da seção 29.9.5, antes de qualquer pedido.
    dialog: {
      title: "Falar com uma pessoa da equipe",
      intro:
        "Uma pessoa da equipe de atendimento do Harborlight vai ler esta conversa para continuar daqui.",
      notShared:
        "A equipe não vê seu nome, seu e-mail nem seu telefone. O que você escrever para a equipe não vai para a IA.",
      noHealth:
        "Não compartilhe dados de saúde, documentos ou dados de outras pessoas. A equipe não dá orientação médica e não informa se alguém está internado.",
      retention:
        "As mensagens do atendimento ficam guardadas com esta conversa e são apagadas em até 90 dias depois do fim do atendimento.",
      confirm: "Chamar a equipe",
      cancel: "Agora não",
      calling: "Chamando…",
    },
    queued: "Você está na fila. Posição {position}.",
    leaveQueue: "Sair da fila",
    assigned: "Você está falando com uma pessoa da equipe do Harborlight.",
    end: "Encerrar atendimento",
    ending: "Encerrando…",
    returned: "Outra pessoa da equipe vai continuar o atendimento.",
    reconnecting: "Reconectando…",
    started: "Atendimento com a equipe do Harborlight",
    composerLabel: "Escreva para a equipe",
    composerNotice:
      "Você está falando com uma pessoa. Não compartilhe dados de saúde nem documentos. Números de documento e de cartão, e-mail e telefone são removidos antes do envio.",
    teamLabel: "Equipe do Harborlight",
    removed: "Removemos esta mensagem para proteger sua privacidade.",
    purged: "O conteúdo deste atendimento foi apagado.",
    sendFailed: "Não foi possível enviar. Tente de novo.",
    continueWithAtrium: "Você pode continuar perguntando ao Atrium.",
    // O texto do divisor de encerramento, pelo motivo (seção 29.5).
    closeReasons: {
      resolved: "Atendimento encerrado pela equipe.",
      redirected: "Atendimento encerrado pela equipe.",
      out_of_scope: "Atendimento encerrado pela equipe.",
      no_response: "Atendimento encerrado pela equipe.",
      abusive:
        "Atendimento encerrado. O atendimento por uma pessoa fica indisponível para você por 24 horas.",
      visitor_cancelled: "Você saiu da fila.",
      visitor_ended: "Você encerrou o atendimento.",
      queue_timeout:
        "Ninguém da equipe conseguiu responder agora. Você pode ligar para a mesa telefônica no (555) 014-2600.",
      visitor_left:
        "Ninguém da equipe conseguiu responder agora. Você pode ligar para a mesa telefônica no (555) 014-2600.",
      service_closed:
        "Ninguém da equipe conseguiu responder agora. Você pode ligar para a mesa telefônica no (555) 014-2600.",
      inactivity: "Atendimento encerrado por falta de mensagens.",
    },
  },
  // Console da equipe, `/attendance` e `/attendance/commitment` (seções
  // 29.3 e 29.11): `PresenceToggle`, `QueueList`, `HandoffThread`,
  // `RedactDialog` e a tela do compromisso.
  attendance: {
    presenceLabel: "Sua presença",
    available: "Disponível",
    away: "Ausente",
    stats: {
      queued: "Na fila",
      mine: "Comigo",
      available: "Equipe disponível",
    },
    queueTitle: "Fila",
    queueLabel: "Visitantes na fila",
    emptyQueue: "Nenhum visitante na fila.",
    awayNotice:
      "Você está como ausente. Marque Disponível para receber atendimentos.",
    take: "Assumir",
    taking: "Assumindo…",
    atCapacity: "Você já tem 3 atendimentos. Encerre ou devolva um antes.",
    taken: "Outra pessoa já assumiu este atendimento.",
    waiting: "Esperando há {time}",
    justNow: "menos de 1 minuto",
    minutesOne: "1 minuto",
    minutesMany: "{minutes} minutos",
    returned: "Devolvido",
    // O selo do canal e o status de entrega no WhatsApp (seções 30.5 e 30.11).
    whatsapp: "WhatsApp",
    delivery: {
      pending: "Enviando…",
      sent: "Enviada",
      delivered: "Entregue",
      read: "Lida",
      failed: "Não entregue",
    },
    whatsappComposer:
      "A mensagem vai pelo WhatsApp. Sem formatação e sem anexos.",
    visitorAway: "Visitante ausente",
    visitorPresent: "Visitante na conversa",
    // Os rótulos do motivo da oferta (seção 29.11).
    triggers: {
      abstained: "Não estava nas informações publicadas",
      grounding_failed: "A IA não confirmou a resposta",
      off_topic: "Fora do tema da IA",
      degraded: "IA indisponível",
      error: "IA indisponível",
      not_helpful: "Resposta marcada como não útil",
    },
    handoffsLabel: "Seus atendimentos",
    noHandoffs: "Nenhum atendimento com você agora.",
    conversationTitle: "Conversa com o Atrium",
    handoffTitle: "Mensagens do atendimento",
    visitorLabel: "Visitante",
    atriumLabel: "Atrium",
    teamLabel: "Equipe do Harborlight",
    healthMarker: "Mensagem de saúde, não guardada.",
    removedMessage: "Mensagem removida ({category}).",
    composerLabel: "Responder ao visitante",
    composerHint:
      "Responda só com informação pública do Harborlight. Não dê orientação médica nem confirme quem está internado.",
    placeholder: "Escreva a resposta",
    send: "Enviar",
    sending: "Enviando…",
    emergency: "Enviar orientação de emergência",
    redact: "Remover conteúdo",
    redactTitle: "Remover o conteúdo desta mensagem",
    redactDescription:
      "O texto é apagado na hora, sem cópia. O visitante vê um aviso no lugar.",
    redactCategory: "Categoria",
    redactConfirm: "Remover",
    categories: {
      health: "Dado de saúde",
      document: "Documento",
      contact: "Contato",
      third_party: "Dado de outra pessoa",
      other: "Outro",
      retention: "Prazo de retenção",
    },
    release: "Devolver à fila",
    close: "Encerrar",
    closeTitle: "Encerrar o atendimento",
    closeDescription:
      "Escolha o motivo. O visitante vê o aviso de encerramento e volta a conversar com o Atrium.",
    closeReasonLabel: "Motivo",
    closeReasonPlaceholder: "Escolha um motivo",
    closeConfirm: "Encerrar atendimento",
    cancel: "Cancelar",
    closeReasons: {
      resolved: "Respondido",
      redirected: "Encaminhado para a mesa telefônica ou outro canal",
      out_of_scope: "Fora do que a equipe atende",
      no_response: "O visitante não respondeu",
      abusive: "Ofensa ou assédio",
    },
    statusClosed: "Atendimento encerrado.",
    reconnecting: "Reconectando…",
    titleCount: "({count}) Atendimento · Atrium",
    actionFailed: "Não foi possível concluir a ação.",
    // O compromisso de confidencialidade da seção 29.3.
    commitment: {
      lead: "Antes de assumir o primeiro atendimento, e a cada versão nova, leia e aceite o compromisso abaixo (versão {version}).",
      items: [
        "Uso o que leio só para responder a esta pessoa, neste atendimento.",
        "Respondo só com informação pública do Harborlight. O catálogo da seção 9 é a referência de horários e telefones.",
        "Não dou orientação médica. Num assunto de sintoma, dose, exame ou remédio, uso a ação Enviar orientação de emergência, que manda o texto fixo de orientação.",
        "Nunca confirmo nem nego que alguém está internado ou é paciente, e não informo quarto, estado, exame ou alta.",
        "Nunca peço documento, cartão, senha, endereço, e-mail ou telefone. O atendimento não tem retorno por fora.",
        "Assunto de uma pessoa específica, como cobrança, exame ou internação, vai para o telefone do setor. Pedido sobre dados pessoais vai para o canal de privacidade, em /privacy.",
        "Removo, com a categoria, a mensagem que traz dado de saúde, documento ou dado de outra pessoa.",
        "Não copio, não fotografo e não repasso o conteúdo do console.",
        "Encerro como abuso uma conversa com ofensa ou assédio.",
        "Saio da conta ao deixar o computador.",
      ],
      checkbox: "Li e aceito o compromisso",
      accept: "Aceitar e continuar",
      accepting: "Aceitando…",
    },
  },
  // Atendimentos encerrados do admin, `/admin/attendance` (seção 29.11).
  adminAttendance: {
    description:
      "Atendimentos encerrados, sem conteúdo. Para ler um deles, escreva o motivo: ele fica na auditoria.",
    periodLabel: "Período",
    period7: "7 dias",
    period30: "30 dias",
    columns: {
      label: "Atendimento",
      trigger: "Motivo da oferta",
      wait: "Espera",
      duration: "Duração",
      closeReason: "Encerramento",
      purged: "Texto",
      actions: "Ações",
    },
    purgedYes: "Apagado",
    purgedNo: "Guardado",
    open: "Abrir",
    empty: "Nenhum atendimento encerrado no período.",
    reasonTitle: "Por que você vai abrir este atendimento?",
    reasonLabel: "Motivo",
    reasonHint:
      "De 10 a 500 caracteres. Por exemplo: apurar uma reclamação ou um pedido de titular.",
    reasonError: "Escreva o motivo com 10 a 500 caracteres.",
    confirm: "Abrir atendimento",
    opening: "Abrindo…",
    sheetTitle: "Atendimento {label}",
    sheetDescription: "Leitura registrada na auditoria. Só leitura.",
    closeReasons: {
      resolved: "Respondido",
      redirected: "Encaminhado",
      out_of_scope: "Fora do escopo",
      no_response: "Sem resposta do visitante",
      abusive: "Abuso",
      visitor_cancelled: "Visitante saiu da fila",
      visitor_ended: "Visitante encerrou",
      queue_timeout: "Espera vencida",
      visitor_left: "Visitante ausente",
      service_closed: "Serviço desligado",
      inactivity: "Sem mensagens",
    },
  },
} as const
