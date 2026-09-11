# open-ek75

[English](README.md) · **Português (Brasil)**

**Configure a iluminação RGB de um teclado Dareu TK51G/EK75 — vendido no Brasil
como Husky Nomadic — no Linux, sem precisar do Windows.** Leia o efeito, a cor e
o brilho reais de cada zona de iluminação e mude qualquer um deles, por uma
interface gráfica ou pela linha de comando.

A Dareu (a fabricante de fato do chip e do firmware) publica uma ferramenta de
configuração **na web**, [dr.dareu.com](https://dr.dareu.com/), que fala com o
teclado direto do Chrome via WebHID — não existe app nativo, nem para Windows.
Este projeto porta a lógica de protocolo dessa ferramenta para Python: o
JavaScript foi decompilado (é minificado, mas não ofuscado — todo nome de
classe, método e constante sobrevive) e cada pacote que este código envia foi
reproduzido em hardware real antes de entrar no repositório.

Escrito em Python puro, para **Linux** (controla o teclado através do
`hidraw`). **Zero dependências** — só a biblioteca padrão, incluindo a interface
gráfica, que é tkinter.

> Sem afiliação com a Dareu, a Husky ou qualquer outra marca sob a qual este
> teclado seja vendido, e sem endosso delas. Use por sua conta e risco.

## Funciona com o seu teclado?

Rode `lsusb` e procure por **`260d:0101`**:

```
Bus 003 Device 003: ID 260d:0101  EK75_Keyboard
```

Essa combinação de chip e firmware é um projeto de referência da Dareu
(internamente chamado **TK51G**, vendido no varejo como **EK75**) que várias
marcas revendem com nome próprio. Confirmados até agora:

| Marca | Modelo(s) |
|-------|-----------|
| Dareu | TK51G / EK75 |
| Husky (Kabum, Brasil) | **Nomadic** — HTG200 / HTG500 / HTG800 V2 |

O nome da caixa e o nome no firmware são diferentes, o que vale saber se você
está pesquisando: a Husky vende como **Nomadic**, enquanto o teclado só se
identifica como `TK51G` / `EK75`. "Nomadic" não aparece em lugar nenhum do
driver da Dareu, do perfil de dispositivo dela nem dos binários do aplicativo
Windows — é branding de varejo da Husky sobre um projeto de referência da Dareu.

Se o `lsusb` do seu teclado mostrar um PID **diferente** sob o fabricante
`260D`, veja `https://dr.dareu.com/products/<PID>/<PID>.json` — se ele existir e
o `"FwType"` for `0`, este mesmo código provavelmente funciona sem alteração
(veja o [PROTOCOL.md](PROTOCOL.md) para o que o `FwType` muda). Um `FwType`
diferente exige outro Report ID e outro tamanho, coisa que o
`ek75/core/device.py` já não fixa de forma errada — mas a assinatura de
descritor do `find_device()` foi escrita contra o dispositivo `FwType: 0` e pode
precisar de ajuste.

> **Conecte o teclado pelo cabo USB para configurá-lo.** Este modelo também
> funciona por um dongle 2.4G, e a configuração não funciona assim — o teclado
> não responde, e o `open-ek75` vai dizer que não o encontrou. Três coisas
> distintas concordam nisso: o JavaScript do próprio fabricante troca de Report
> ID quando o `WirelessFlag` dele indica 2.4G, o aplicativo Windows esconde um
> painel inteiro de ajustes (`gdDisableWl`) quando a conexão é sem fio, e o dono
> da unidade em que isto foi construído confirmou na prática. Uma vez gravado
> pelo cabo, o ajuste fica na memória do próprio teclado — dá para desconectar e
> voltar para o sem fio depois.

## O que funciona

- **Uma interface gráfica** (`open-ek75 gui`) com o teclado desenhado a partir
  do perfil de dispositivo da própria Dareu — 83 teclas na geometria do
  fabricante, knob de volume incluído — prévia animada do efeito selecionado e
  todos os controles de iluminação numa tela só. **Inglês ou português do
  Brasil**, alternado pelo cabeçalho e lembrado entre execuções.
- **Um guia dos atalhos com Fn**, na página Dispositivo. Este teclado tem 38
  deles e não imprime nenhum no case; são decodificados do mapa de teclas que o
  próprio teclado traz, então a lista é do hardware e não um chute. `Fn` + `I` é
  Print Screen, `Fn` + `Espaço` cicla o brilho, e assim por diante.
- **Leitura** do estado real de cada zona: efeito, cor(es), velocidade, brilho —
  não apenas o que esta ferramenta escreveu por último.
- **Perguntar ao teclado quais efeitos cada zona suporta**
  (`LED_CMD_ATTRIBUTE`) e quais zonas existem (`LED_CMD_ID_LIST`), em vez de
  oferecer os 33 efeitos e torcer. Isso importa mais do que parece: na unidade
  em que o projeto foi construído, o firmware reporta quatro efeitos que o
  próprio perfil de dispositivo do fabricante omite, e não tem um que o perfil
  oferece.
- **Os nomes de efeito do próprio fabricante**, em inglês e em português, tirados
  da tabela de textos do software oficial — então "Difusão" aqui é o mesmo
  efeito que "Difusão" lá, mesmo o protocolo chamando de `Rotate`.
- **Modo RGB** — enviar uma lista de cores vazia é como o protocolo diz "escolhe
  você", que é o arco-íris que o software oficial chama de RGB e o que este
  teclado traz de fábrica no `Wave`. O seletor de cor oferece isso como uma
  amostra.
- **Uma prévia que bate com o hardware**, não uma aproximação: a rampa de
  arco-íris e o padrão fixo da luz lateral são as tabelas de cor do próprio
  firmware, extraídas do software do fabricante em vez de adivinhadas com HSV.
- **Aplicar** `Static` (cor sólida) e `Breathing` (cor pulsante) em qualquer
  zona, com qualquer cor RGB — além dos outros efeitos que o seu teclado reporta
  como suportados, que estão portados mas não foram confirmados um a um no
  hardware.
- **Brilho e velocidade nas faixas que o hardware realmente usa** — brilho como
  porcentagem de um byte 0-255 (que é como funciona o slider 1-100 do software
  oficial) e velocidade 1-3 em vez de 0-255. Os dois vieram de decompilar o
  aplicativo Windows do fabricante, uma implementação independente do mesmo
  protocolo; veja [PROTOCOL.md](PROTOCOL.md), "A second vendor source".
- **Honesto sobre o que não funciona.** O byte `Flag` do pacote é a direção da
  animação no software do fabricante, e este firmware guarda o byte fielmente —
  mas foi testado e **confirmado que não o renderiza**. O controle continua
  visível, com essa informação, porque o pacote está correto e um modelo irmão
  pode respeitá-lo. O mesmo vale para a luz lateral no `Static`, que acende mas
  desenha um padrão fixo e ignora a cor enviada.
- **Backup e restauração** de todo o estado de iluminação num arquivo JSON, para
  que um teste que não ficou bom esteja a um comando de ser desfeito. A
  interface gráfica faz um backup automático na primeira vez que conecta.

Duas zonas de iluminação estão confirmadas no teclado em que isto foi construído
(uma unidade Husky da linha HTG): a região `1` é a matriz por tecla (uma grade
de 6x15 LEDs) e a região `4` é a barra de luz lateral (uma fita de 16).
`open-ek75 probe` pergunta ao seu próprio teclado quais zonas ele tem e quais
efeitos cada uma suporta.

**Ler está mais adiantado do que escrever**, e a separação é proposital: uma
leitura errada devolve uma resposta errada, enquanto uma escrita errada pode
deixar um teclado físico num estado do qual não se sai.

*Implementado, somente leitura*: nível de bateria e temporizador de suspensão,
o mapa de teclas (`keys` — o que cada tecla faz nas duas camadas, lido do
teclado e não do perfil do fabricante, que discorda deste hardware em 23
atribuições), quais perfis existem e qual está ativo, e as macros guardadas
(`probe`).

Esta última merece uma frase: o perfil de dispositivo da Dareu não contém a
palavra "macro", e o teclado em que isto foi construído tem uma guardada mesmo
assim. Os bytes aparecem crus porque o formato não foi decodificado — o código
que os monta não está em nenhum arquivo do fabricante que este projeto tem, e um
palpite sobre as teclas seria um formato inventado.

*Implementado, e escreve*: a iluminação, e **remapear uma tecla** pela página
Teclas da interface — escolha a tecla, escolha a camada, e atribua outra tecla
(com Ctrl/Shift/Alt/Win se quiser), uma tecla de mídia, ou o que outra tecla do
seu teclado já faz. O `backup` grava o mapa de teclas junto com a iluminação e o
`restore` devolve os dois; use `--keys-only` ou `--lighting-only` para mexer só
em um deles.

Nada é gravado antes de existir um backup do mapa, e duas teclas nunca podem ser
remapeadas: as que carregam o `Fn` e o reset de fábrica. Juntas elas são o
**`Fn`+`Esc`, um reset de fábrica embutido no firmware** — o caminho de volta que
não depende deste software, e que remapear qualquer uma das duas destruiria.

**Não implementado**: mapas de cor por tecla, gravar ou editar macros, e criar
ou trocar de perfil. Este último merece ser dito sem rodeios: o
aplicativo oficial do Windows mostra Perfil 1/2/3, e este teclado reporta
exatamente um. Os outros dois não estão escondidos — eles não existem, e
criá-los é uma escrita persistente cujo desfazer nunca foi testado. A interface
mostra os itens não implementados nomeados como tais, em vez de escondê-los,
cada um dizendo de qual classe de comando precisaria.
Veja o [PROTOCOL.md](PROTOCOL.md) — em especial "What is not implemented yet" e
"What to try next" — para o mapa completo do que é conhecido mas não portado,
versus o que é genuinamente desconhecido.

## Requisitos

Linux, Python 3.8+, sem dependências.

## Instalação

A partir de um clone deste repositório:

```bash
git clone https://github.com/mateusands/open-ek75 && cd open-ek75
sudo sh packaging/install.sh
```

Isso instala uma regra udev para `260d:0101` de modo que o nó HID do teclado
fique utilizável sem root, usando `TAG+="uaccess"` — o mesmo mecanismo moderno
do systemd/logind que o `open-m711pro` usa, e pela mesma razão: entrega o
dispositivo ao usuário da sessão local ativa em vez de deixá-lo gravável por
todo mundo para sempre com `MODE="0666"`. Veja os comentários em
[packaging/60-ek75.rules](packaging/60-ek75.rules) para os detalhes e para uma
alternativa em sistemas sem `systemd-logind`. Reconecte o teclado depois.

Opcionalmente, `pip install --user .` deixa o comando `open-ek75` disponível no
seu `PATH` — rodar a partir do clone com `python3 main.py` não exige instalação
nenhuma.

## Uso

### Interface gráfica

```bash
python3 main.py gui        # ou `open-ek75 gui`, ou `open-ek75-gui`, depois de instalar
```

Abre em **Dispositivo**: o que é este teclado, backup/restauração e a lista
completa de atalhos com Fn. As outras três páginas seguem o formato do software
oficial — **Iluminação** (a que funciona), **Teclas** e **Macros** (não
implementadas; elas dizem isso, e dizem de qual classe de comando precisariam).

O seletor de idioma é o par `EN` / `PT-BR` no cabeçalho. O padrão é inglês e a
sua escolha fica guardada em `~/.config/open-ek75/settings.json`;
`OPEN_EK75_LANG=pt` sobrepõe isso para uma execução.

A página de iluminação pergunta ao teclado quais efeitos cada zona suporta e
mostra só esses, e exibe um controle apenas quando o efeito selecionado o
possui — sem slider de velocidade no `Static`, sem setas de direção em nada além
do `Wave` — que é o que o software oficial faz, pelo mesmo motivo.

### Linha de comando

```bash
python3 main.py probe                # só leitura: zonas, efeitos suportados e estado
python3 main.py regions              # lê o estado atual de cada zona
python3 main.py set 1 static ff0000  # matriz de teclas: vermelho sólido
python3 main.py set 4 static 00c8ff  # luz lateral: azul-ciano sólido
python3 main.py set 1 breathing 00ff00 --speed 2
python3 main.py set 1 wave --speed 2          # sem cor = o arco-íris do firmware
python3 main.py set 1 wave --speed 3 --flag 1 # direção: leia o PROTOCOL.md antes de confiar
python3 main.py brightness 1 60 --percent     # ou `brightness 1 153` para o byte cru
python3 main.py off 4                # apaga a luz lateral

python3 main.py backup                       # salva tudo em ~/.config/open-ek75/backup.json
python3 main.py backup meu.json              # ...ou num arquivo que você escolher
python3 main.py restore                      # devolve tudo

python3 main.py watch 1                      # só leitura: mostra a zona 1 mudando
```

O `watch` não escreve nada. Rode e aperte os atalhos de iluminação com Fn do
próprio teclado: ele mostra qual campo do protocolo o firmware mexeu. É assim
que as incógnitas restantes se resolvem sem mandar ao hardware um byte que
ninguém validou — veja [PROTOCOL.md](PROTOCOL.md), "What to try next".

O `set` recebe o número da região, um efeito (pelo nome — `static`, `breathing`,
`wave`, `off`, ou qualquer um dos 33 do [PROTOCOL.md](PROTOCOL.md) — ou um
número cru) e uma cor R G B como três argumentos separados (`0` `255` `0`).
**Omita a cor** e o firmware escolhe a dele, que é a forma arco-íris dos efeitos
animados.

O `--speed` vai de 1 a 3 (2 é o "normal" do fabricante) e só alguns efeitos o
usam. O `--flag` é a direção da animação, 0 ou 1 — o software do fabricante o
trata assim e este firmware guarda o valor fielmente, mas foi confirmado que
**não** o renderiza; o `PROTOCOL.md` tem a história completa. O `brightness`
recebe um byte cru de 0 a 255, ou 0 a 100 com `--percent`, que é a escala
mostrada pelo slider do software oficial.

**Rode `backup` antes de experimentar.** O estado de iluminação é gravado na
memória persistente do teclado — desconectar o cabo ou desligar o computador não
desfaz a mudança. O `restore` é o caminho de volta.

## Estrutura do projeto

Veja o [README em inglês](README.md#project-layout), que é onde a árvore de
diretórios é mantida — duplicá-la aqui só criaria duas versões para
dessincronizar.

A regra de camadas, a mesma do `open-m711pro`: `core/protocol.py` é lógica pura
e é o que os testes de byte exercitam; `core/device.py` é o único módulo que
toca o hardware; nem o `cli.py` nem nada dentro de `gui/` monta um pacote —
os dois passam pelo `core/lighting.py`.

## Protocolo

O texto completo, incluindo como o protocolo foi recuperado (decompilando o
driver web público da Dareu e, depois, o aplicativo Windows da Husky — não uma
captura USB) e tudo o que continua sem mapear, está no
[PROTOCOL.md](PROTOCOL.md), em inglês. Resumo:

**Feature Reports** HID de 64 bytes, sem Report ID declarado pelo dispositivo (o
Linux ainda exige um byte `0x00` de prefixo para o ioctl, então os buffers aqui
têm 65 bytes), enviados via `ioctl(HIDIOCSFEATURE)` e lidos via
`ioctl(HIDIOCGFEATURE)` no único nó `/dev/hidraw*` (de cinco) que expõe essa
interface do fabricante.

```
byte 0  TargetId (0 = com fio)          byte 4  Perfil (1 = padrão)
byte 1  tamanho do payload              byte 5  (não usado)
byte 2  classe de comando (3 = Lighting) byte 6+ payload
byte 3  subcomando | 0x80 (get) ou | 0x00 (set)
```

Aplicar um efeito: `região, efeito, flag, velocidade, número de cores,
[R,G,B]...` no payload. O dispositivo responde de forma assíncrona — o comando é
enviado e então o `GET_FEATURE` é consultado até o byte de status dizer
"pronto".

## Desenvolvimento

```bash
python3 -m pytest              # testes de byte (se o pytest estiver instalado)
python3 tools/run_tests.py     # os mesmos testes sem o pytest
```

A mesma disciplina do `open-m711pro`: **nenhum pacote é enviado ao hardware sem
ter sido reproduzido e confirmado visualmente, ou lido de volta do
dispositivo.** Todo construtor do `protocol.py` tem um teste de byte que o
prende a um payload que ou produziu um efeito visual confirmado, ou bate com um
valor lido de hardware real — veja as docstrings em `tests/test_protocol.py`
para saber qual é qual; nem tudo ali é captura crua como nos testes do
`open-m711pro`, porque este protocolo veio de código-fonte e não de um
`.pcapng`.

## Créditos

O protocolo é da própria Dareu — recuperado do driver web público em
`dr.dareu.com` e do aplicativo Windows da Husky onde o driver web era omisso, em
vez de tráfego USB (compare com o `open-m711pro`, onde não existia ferramenta do
fabricante e tudo veio de capturar pacotes). Nenhum arquivo do fabricante é
redistribuído aqui e nenhuma arte deles é usada: o teclado que esta interface
desenha é construído a partir da geometria de layout do perfil de dispositivo
público da própria Dareu. O porte para Python, a varredura de descoberta de
regiões e a confirmação em hardware são trabalho deste repositório.

## Licença

[GPL-3.0](LICENSE).
