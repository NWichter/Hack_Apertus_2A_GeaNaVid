"""Hand-written spec of the synthetic hold-out set (generator: Claude).

SECTIONS cut the reference text out of the cleaned PDF pages: each part is
(page, start_anchor, end_anchor); the end anchor is included.
ROWS: (id, section, label, claim_language, claim, [(page, evidence_text), ...]).
"""

BOOKLETS = {
    "2019-02-10": "feT3z55YdiNa",
    "2019-05-19": "JidqjDWbXbrM",
    "2018-06-10": "WBiy0Vj6fgqY",
}

URL_NAME = {
    "de": "erlaeuterungen_des_bundesrates",
    "fr": "explications_du_conseil_federal",
    "it": "spiegazioni_del_consiglio_federale",
}


def booklet_url(date: str, lang: str) -> str:
    return f"https://www.bk.admin.ch/dam/{lang}/sd-web/{BOOKLETS[date]}/{date}_{URL_NAME[lang]}.pdf"


VOTES = {
    (
        "Z",
        "de",
    ): "Volksinitiative «Zersiedelung stoppen – für eine nachhaltige Siedlungsentwicklung (Zersiedelungsinitiative)»",
    (
        "Z",
        "fr",
    ): "Initiative populaire « Stopper le mitage – pour un développement durable du milieu bâti (initiative contre le mitage) »",
    (
        "Z",
        "it",
    ): "Iniziativa popolare «Fermare la dispersione degli insediamenti – per uno sviluppo insediativo sostenibile (Iniziativa contro la dispersione degli insediamenti)»",
    ("S", "de"): "Bundesgesetz über die Steuerreform und die AHV-Finanzierung (STAF)",
    (
        "S",
        "fr",
    ): "Loi fédérale relative à la réforme fiscale et au financement de l’AVS (RFFA)",
    (
        "S",
        "it",
    ): "Legge federale concernente la riforma fiscale e il finanziamento dell’AVS (RFFA)",
    (
        "W",
        "de",
    ): "Umsetzung einer Änderung der EU-Waffenrichtlinie (Weiterentwicklung von Schengen)",
    (
        "W",
        "fr",
    ): "Mise en œuvre d’une modification de la directive de l’UE sur les armes (Développement de l’acquis de Schengen)",
    (
        "W",
        "it",
    ): "Trasposizione nel diritto svizzero di una modifica della direttiva UE sulle armi (Sviluppo di Schengen)",
    (
        "V",
        "de",
    ): "Volksinitiative «Für krisensicheres Geld: Geldschöpfung allein durch die Nationalbank! (Vollgeld-Initiative)»",
    (
        "V",
        "fr",
    ): "Initiative populaire « Pour une monnaie à l’abri des crises : émission monétaire uniquement par la Banque nationale ! (Initiative Monnaie pleine) »",
    (
        "V",
        "it",
    ): "Iniziativa popolare «Per soldi a prova di crisi: emissione di moneta riservata alla Banca nazionale! (Iniziativa Moneta intera)»",
    ("G", "de"): "Bundesgesetz über Geldspiele (Geldspielgesetz)",
    ("G", "fr"): "Loi fédérale sur les jeux d’argent",
    ("G", "it"): "Legge federale sui giochi in denaro",
}

VOTE_DATE = {
    "Z": "2019-02-10",
    "S": "2019-05-19",
    "W": "2019-05-19",
    "V": "2018-06-10",
    "G": "2018-06-10",
}

# key: (vote, lang, [(page, start, end), ...])
SECTIONS = {
    # 2019-02-10 Zersiedelung
    "Z_de_kurz": (
        "Z",
        "de",
        [(4, "In der Schweiz wird rege gebaut.", "Arbeitens fördern.")],
    ),
    "Z_de_br": (
        "Z",
        "de",
        [
            (
                14,
                "Natur und Landschaft zu erhalten, ist wichtig.",
                "verstärkt die Zersiedelung.",
            ),
            (15, "Die Initiative widerspricht dem Föderalismus", "abzulehnen."),
        ],
    ),
    "Z_de_kom": (
        "Z",
        "de",
        [
            (12, "Unseren Boden schützen.", "ausserhalb der Bauzonen weitergeht."),
            (
                13,
                "Mit der Initiative ist Bauen weiterhin möglich.",
                "JA zur Zersiedelungsinitiative.",
            ),
        ],
    ),
    "Z_de_text": (
        "Z",
        "de",
        [
            (
                16,
                "Die Bundesverfassung wird wie folgt geändert:",
                "geringfügig umgenutzt werden.",
            )
        ],
    ),
    "Z_fr_cf": (
        "Z",
        "fr",
        [
            (
                14,
                "Il est important de préserver la nature et le paysage.",
                "renforce encore le mitage du territoire.",
            ),
            (
                15,
                "L’initiative contrevient aux principes du fédéralisme",
                "(initiative contre le mitage) ».",
            ),
        ],
    ),
    "Z_fr_ctx": (
        "Z",
        "fr",
        [(7, "La croissance démographique et économique", "n’aura pas été approuvé.")],
    ),
    "Z_fr_kom": (
        "Z",
        "fr",
        [
            (12, "Protégeons nos sols.", "en dehors des zones à bâtir."),
            (
                13,
                "L’initiative n’empêche pas toute construction.",
                "votez OUI à l’initiative contre le mitage.",
            ),
        ],
    ),
    "Z_it_kurz": (
        "Z",
        "it",
        [
            (
                4,
                "In Svizzera si costruisce senza sosta",
                "forme abitative e lavorative sostenibili.",
            )
        ],
    ),
    "Z_it_forder": ("Z", "it", [(9, "Depositata nel 2016", "ristoranti di montagna.")]),
    "Z_it_attu": (
        "Z",
        "it",
        [(10, "Un altro obiettivo dei promotori", "dalla loro ridistribuzione.")],
    ),
    "Z_it_cf": (
        "Z",
        "it",
        [
            (
                14,
                "È importante preservare la natura e il paesaggio, ma l’iniziativa non presenta alcun vantaggio per il nostro Paese. Un rigido",
                "favorendo così la dispersione degli insediamenti.",
            ),
            (
                15,
                "L’iniziativa è in contrasto con il federalismo",
                "(Iniziativa contro la dispersione degli insediamenti)».",
            ),
        ],
    ),
    "Z_it_kom": (
        "Z",
        "it",
        [
            (12, "Preservare il nostro suolo.", "al di fuori delle zone edificabili."),
            (
                13,
                "L’iniziativa non impedisce di continuare a costruire.",
                "votate SÌ all’iniziativa contro la dispersione degli insediamenti.",
            ),
        ],
    ),
    # 2019-05-19 STAF
    "S_de_kurz": (
        "S",
        "de",
        [
            (
                4,
                "Für den Wohlstand unseres Landes",
                "als Beitrag zur Sicherung der Renten.",
            )
        ],
    ),
    "S_de_detail": (
        "S",
        "de",
        [(10, "Mit der Vorlage gelten künftig", "zu einer höheren Steuerbelastung.")],
    ),
    "S_de_tab": ("S", "de", [(15, "Ab 2020 fliessen", "auf 1000 Franken Lohn.")]),
    "S_de_kom": (
        "S",
        "de",
        [
            (
                16,
                "Die Vorlage zur Steuerreform und AHV-Finanzierung (STAF) ist ebenso inakzeptabel",
                "damit es bis zum Monatsende reicht.",
            ),
            (17, "Anstatt den grossen Unternehmen", "NEIN zum erneuten Steuerbschiss!"),
        ],
    ),
    "S_fr_kurz": (
        "S",
        "fr",
        [
            (
                4,
                "Une fiscalité des entreprises compétitive",
                "pour contribuer à garantir les rentes.",
            )
        ],
    ),
    "S_fr_detail": (
        "S",
        "fr",
        [
            (
                10,
                "Si le projet est accepté, les entreprises",
                "la charge fiscale des actionnaires.",
            )
        ],
    ),
    "S_fr_avs": (
        "S",
        "fr",
        [(11, "Le projet fournira à l’AVS", "augmenteront chacun de 0,15 point.")],
    ),
    "S_fr_cf": (
        "S",
        "fr",
        [
            (
                18,
                "La loi fédérale relative à la réforme fiscale et au financement de l’AVS (RFFA) constitue",
                "seront comblées.",
            ),
            (19, "Le projet encourage la recherche", "financement de l’AVS (RFFA)."),
        ],
    ),
    "S_it_kurz": (
        "S",
        "it",
        [
            (
                4,
                "Un’imposizione delle imprese competitiva",
                "quale contributo per garantire le rendite.",
            )
        ],
    ),
    "S_it_tab": (
        "S",
        "it",
        [(15, "Dal 2020 saranno versati", "su ogni 1000 franchi di salario.")],
    ),
    "S_it_cf": (
        "S",
        "it",
        [
            (
                18,
                "La legge federale concernente la riforma fiscale e il finanziamento dell’AVS offre",
                "saranno inoltre colmate.",
            ),
            (
                19,
                "Il progetto promuove le attività di ricerca",
                "finanziamento dell’AVS (RFFA).",
            ),
        ],
    ),
    # 2019-05-19 Waffenrichtlinie
    "W_de_massn": (
        "W",
        "de",
        [(37, "Das Schweizer Waffenrecht will", "bekommt dann auch bei uns keine.")],
    ),
    "W_de_semi": (
        "W",
        "de",
        [
            (
                38,
                "Mit der Teilrevision des Waffengesetzes",
                "ändert sich ebenfalls nichts.",
            )
        ],
    ),
    "W_de_br": (
        "W",
        "de",
        [
            (
                44,
                "Die Einwohnerinnen und Einwohner der Schweiz vor Waffengewalt schützen",
                "können weiterhin stattfinden.",
            ),
            (
                45,
                "Die Teilrevision ermöglicht es der Schweiz",
                "Änderung der EU-Waffenrichtlinie.",
            ),
        ],
    ),
    "W_fr_ctx": (
        "W",
        "fr",
        [
            (
                37,
                "La législation suisse sur les armes entend protéger",
                "aucune arme dans notre pays.",
            )
        ],
    ),
    "W_fr_semi": (
        "W",
        "fr",
        [(38, "Le projet classe notamment", "pour les chasseurs.")],
    ),
    "W_fr_trad": (
        "W",
        "fr",
        [
            (
                39,
                "Lors de l’élaboration de la modification",
                "ne seront pas non plus menacés.",
            )
        ],
    ),
    "W_fr_cf": (
        "W",
        "fr",
        [
            (
                44,
                "Le but de la législation suisse sur les armes",
                "nos manifestations de tir traditionnelles.",
            ),
            (
                45,
                "La révision partielle de la loi permet",
                "de la directive de l’UE sur les armes.",
            ),
        ],
    ),
    "W_it_kurz": (
        "W",
        "it",
        [
            (
                6,
                "Il diritto svizzero in materia di armi, così come",
                "la tradizione svizzera del tiro.",
            )
        ],
    ),
    "W_it_semi": (
        "W",
        "it",
        [(38, "Con la revisione parziale della legge sulle armi", "non cambia nulla.")],
    ),
    "W_it_trad": (
        "W",
        "it",
        [(39, "Nell’elaborazione della modifica", "«Tiro Storico San Gottardo».")],
    ),
    "W_it_cf": (
        "W",
        "it",
        [
            (
                44,
                "Proteggere gli abitanti della Svizzera",
                "potranno continuare a svolgersi.",
            ),
            (45, "Grazie alla revisione parziale", "della direttiva UE sulle armi."),
        ],
    ),
    # 2018-06-10 Vollgeld
    "V_de_kurz": ("V", "de", [(5, "Die Vollgeld", "wirksamere Massnahmen ergriffen.")]),
    "V_de_p7": (
        "V",
        "de",
        [
            (
                7,
                "Zweitens verlangt die Initiative",
                "auf die Kundinnen und Kunden überwälzen.",
            )
        ],
    ),
    "V_de_kom": ("V", "de", [(13, "Vollgeld ist nichts Neues.", "Unsere Zukunft.")]),
    "V_de_br": (
        "V",
        "de",
        [
            (14, "Die Vollgeld", "auf ihre Kundinnen und Kunden überwälzen."),
            (15, "Die Initiative sieht vor, dass die SNB", "lehnen."),
        ],
    ),
    "V_fr_kom": (
        "V",
        "fr",
        [(13, "La monnaie pleine n’est pas une nouveauté.", "Notre avenir.")],
    ),
    "V_fr_cf": (
        "V",
        "fr",
        [
            (14, "L’initiative Monnaie pleine vise à protéger", "sur leur clientèle."),
            (15, "L’initiative prévoit que la BNS", "(Initiative Monnaie pleine) »."),
        ],
    ),
    "V_it_p4": (
        "V",
        "it",
        [
            (
                4,
                "Consiglio federale e Parlamento raccomandano di respingere",
                "1 astensione.",
            )
        ],
    ),
    "V_it_kurz": (
        "V",
        "it",
        [(5, "All’origine dell’iniziativa", "rafforzare la stabilità finanziaria.")],
    ),
    "V_it_kom": (
        "V",
        "it",
        [(13, "La moneta intera non è affatto una novità", "Il nostro futuro.")],
    ),
    "V_it_cf": (
        "V",
        "it",
        [
            (
                14,
                "L’iniziativa Moneta intera si propone",
                "probabilmente riversato sui clienti.",
            ),
            (15, "L’iniziativa prevede che la BNS", "(Iniziativa Moneta intera)»."),
        ],
    ),
    # 2018-06-10 Geldspielgesetz
    "G_de_kurz": (
        "G",
        "de",
        [(17, "Geldspiele wie Roulette", "dem Gemeinwohl zugutekommen.")],
    ),
    "G_de_detail": (
        "G",
        "de",
        [
            (
                18,
                "In der Schweiz werden in Spielbanken",
                "Pokerturniere ausserhalb von",
            ),
            (
                19,
                "Spielbanken mit entsprechender Bewilligung",
                "wäschereigesetz unterstehen.",
            ),
        ],
    ),
    "G_de_kom": (
        "G",
        "de",
        [(23, "Die Schweiz profitiert", "diese Spielerschutz‐Massnahmen.")],
    ),
    "G_de_br": (
        "G",
        "de",
        [
            (
                24,
                "Geldspiele sind eine beliebte Art der Unterhaltung.",
                "300 Millionen Franken.",
            ),
            (
                25,
                "Unternehmen, die in der Schweiz unbewilligte",
                "(Geldspielgesetz) anzunehmen.",
            ),
        ],
    ),
    "G_fr_kurz": (
        "G",
        "fr",
        [(17, "Les jeux d’argent comme la roulette", "doivent servir au bien commun.")],
    ),
    "G_fr_detail": (
        "G",
        "fr",
        [
            (
                18,
                "Les jeux proposés dans les casinos",
                "de nouvelles formes de paris sportifs. En",
            ),
            (
                19,
                "outre, les petits tournois de poker",
                "loi sur le blanchiment d’argent.",
            ),
        ],
    ),
    "G_fr_box": (
        "G",
        "fr",
        [
            (
                21,
                "La loi fédérale sur les jeux d’argent prévoit, à l’article 86",
                "leur offre de jeux non autorisée",
            )
        ],
    ),
    "G_fr_kom": (
        "G",
        "fr",
        [
            (
                23,
                "La Suisse, dont l’économie très développée",
                "ces mesures de protection des joueurs.",
            )
        ],
    ),
    "G_fr_cf": (
        "G",
        "fr",
        [
            (
                24,
                "Les jeux d’argent sont un divertissement répandu.",
                "sur le marché suisse.",
            ),
            (
                25,
                "Les entreprises qui proposent des jeux d’argent en ligne",
                "vous recommandent d’accepter la loi fédérale sur les jeux d’argent.",
            ),
        ],
    ),
    "G_it_detail": (
        "G",
        "it",
        [
            (18, "In Svizzera le case da gioco", "piccoli"),
            (
                19,
                "tornei di poker possono tenersi",
                "la legge sul riciclaggio di denaro.",
            ),
        ],
    ),
    "G_it_kom": (
        "G",
        "it",
        [
            (
                23,
                "Paese con un’economia altamente sviluppata",
                "favorevole a queste misure di protezione.",
            )
        ],
    ),
    "G_it_cf": (
        "G",
        "it",
        [
            (
                24,
                "I giochi in denaro sono un passatempo molto apprezzato",
                "fino a 300 milioni di franchi all’anno.",
            ),
            (
                25,
                "Le società che, attraverso Internet",
                "raccomandano di accettare la legge federale sui giochi in denaro.",
            ),
        ],
    ),
}

E, N, C = 0, 1, 2

ROWS = [
    # ---------- 2019-02-10, DE booklet ----------
    (
        "ho-001",
        "Z_de_kurz",
        E,
        "de",
        "Laut der Zusammenfassung haben die Jungen Grünen die Zersiedelungsinitiative im Jahr 2016 eingereicht.",
        [
            (
                4,
                "Die Jungen Grünen haben 2016 die Volksinitiative «Zersiedelung stoppen – für eine nachhaltige Siedlungsentwicklung (Zersiedelungsinitiative)» eingereicht.",
            )
        ],
    ),
    (
        "ho-002",
        "Z_de_kurz",
        C,
        "fr",
        "Selon le résumé, la révision de la loi sur l’aménagement du territoire acceptée en 2013 limite les zones à bâtir aux besoins prévisibles des 25 prochaines années.",
        [
            (
                4,
                "Bauzonen dürfen nur noch so viel Land umfassen, wie voraussichtlich innert 15 Jahren benötigt wird.",
            )
        ],
    ),
    (
        "ho-003",
        "Z_de_kurz",
        N,
        "it",
        "Secondo il riassunto, l’iniziativa prevede che i Cantoni versino un indennizzo ai proprietari i cui terreni vengono tolti dalla zona edificabile.",
        [],
    ),
    (
        "ho-004",
        "Z_de_br",
        E,
        "de",
        "Der Bundesrat vertritt die Auffassung, dass ein Bauzonen-Stopp jene Kantone und Gemeinden bestraft, die zurückhaltend Bauzonen geschaffen haben.",
        [
            (
                14,
                "Der Bauzonen-Stopp bestraft Kantone und Gemeinden, die sorgsam mit ihrem Boden umgegangen sind und zurückhaltend Bauzonen geschaffen haben.",
            )
        ],
    ),
    (
        "ho-005",
        "Z_de_br",
        C,
        "de",
        "Der Bundesrat ist der Ansicht, dass die Initiative der Landwirtschaft nützt, weil Gewächshäuser und Geflügelhallen künftig leichter auf Landwirtschaftsland gebaut werden können.",
        [
            (15, "Die Initiative schadet der Landwirtschaft."),
            (
                15,
                "Bauten wie Gewächshäuser oder Geflügelhallen dürften grösstenteils nicht mehr auf Landwirtschaftsland erstellt werden.",
            ),
        ],
    ),
    (
        "ho-006",
        "Z_de_br",
        N,
        "fr",
        "Le Conseil fédéral estime que l’initiative ferait augmenter les loyers d’au moins 10 % dans les centres urbains.",
        [],
    ),
    (
        "ho-007",
        "Z_de_kom",
        E,
        "it",
        "Il comitato d’iniziativa afferma che ogni giorno in Svizzera viene edificata una superficie verde grande quanto otto campi da calcio.",
        [
            (
                12,
                "Täglich wird in der Schweiz eine Grünfläche in der Grösse von acht Fussballfeldern überbaut.",
            )
        ],
    ),
    (
        "ho-008",
        "Z_de_kom",
        C,
        "it",
        "Secondo il comitato d’iniziativa, le riserve di terreno edificabile esistenti non basteranno a garantire in futuro spazio abitativo per tutti.",
        [
            (
                13,
                "Die vorhandenen Baulandreserven sind so gross, dass es auch in Zukunft genug Wohnraum für alle geben wird.",
            )
        ],
    ),
    (
        "ho-009",
        "Z_de_kom",
        N,
        "de",
        "Das Komitee ist der Ansicht, dass die Initiative den Pendlerverkehr bis 2040 um ein Viertel reduzieren würde.",
        [],
    ),
    (
        "ho-010",
        "Z_de_text",
        E,
        "fr",
        "Selon le texte soumis au vote, la création de nouvelles zones à bâtir n’est admise que si une autre surface non imperméabilisée d’une taille au moins équivalente est déclassée.",
        [
            (
                16,
                "Die Ausscheidung neuer Bauzonen ist nur zulässig, wenn eine andere unversiegelte Fläche von mindestens gleicher Grösse und vergleichbarem potenziellem landwirtschaftlichem Ertragswert aus der Bauzone ausgezont wird.",
            )
        ],
    ),
    # ---------- 2019-02-10, FR booklet ----------
    (
        "ho-011",
        "Z_fr_cf",
        E,
        "fr",
        "Selon le Conseil fédéral, les cantons dont le plan directeur n’aura pas été approuvé le 30 avril 2019 ne pourront plus créer de zones à bâtir jusqu’à son approbation.",
        [
            (
                14,
                "Les cantons dont le plan directeur n’aura pas été approuvé par le Conseil fédéral le 30 avril 2019 ne pourront plus créer de zones à bâtir jusqu’à ce que le Conseil fédéral donne son approbation.",
            )
        ],
    ),
    (
        "ho-012",
        "Z_fr_cf",
        N,
        "fr",
        "Le Conseil fédéral estime que l’initiative coûterait aux cantons plus de 500 millions de francs par an en indemnités de déclassement.",
        [],
    ),
    (
        "ho-013",
        "Z_fr_cf",
        C,
        "de",
        "Der Bundesrat empfiehlt, die Initiative gegen die Zersiedelung anzunehmen.",
        [
            (
                15,
                "Pour toutes ces raisons, le Conseil fédéral et le Parlement vous recommandent de rejeter l’initiative populaire « Stopper le mitage – pour un développement durable du milieu bâti (initiative contre le mitage) ».",
            )
        ],
    ),
    (
        "ho-014",
        "Z_fr_ctx",
        E,
        "de",
        "Laut den Erläuterungen ist die Bauzonenfläche pro Einwohner um rund 6 Prozent von 309 auf 291 Quadratmeter gesunken.",
        [
            (
                7,
                "La surface de zones à bâtir par habitant a ainsi diminué de quelque 6 %, passant de 309 à 291 m2",
            )
        ],
    ),
    (
        "ho-015",
        "Z_fr_ctx",
        N,
        "de",
        "Laut den Erläuterungen hat der Kanton Wallis seine Bauzonen seit 2013 um mehr als 2000 Hektaren verkleinert.",
        [],
    ),
    (
        "ho-016",
        "Z_fr_ctx",
        C,
        "it",
        "Secondo le spiegazioni, la superficie totale delle zone edificabili in Svizzera ha continuato ad aumentare anche dopo il 2012.",
        [
            (
                7,
                "En Suisse, la surface des zones à bâtir a augmenté sans discontinuer jusqu’en 2012.",
            ),
            (
                7,
                "Ensuite, la tendance s’est inversée, la surface totale des zones à bâtir cessant d’augmenter alors que la population qui y vit est passée de 7,4 à 8 millions d’habitants.",
            ),
        ],
    ),
    (
        "ho-017",
        "Z_fr_kom",
        E,
        "it",
        "Secondo il comitato d’iniziativa, ogni secondo in Svizzera viene edificato quasi un metro quadrato di terreno.",
        [
            (
                12,
                "Chaque seconde, près d’un mètre carré de terrain est construit en Suisse.",
            )
        ],
    ),
    (
        "ho-018",
        "Z_fr_kom",
        N,
        "it",
        "Il comitato d’iniziativa sostiene che l’iniziativa è appoggiata dall’Unione svizzera dei contadini.",
        [],
    ),
    (
        "ho-019",
        "Z_fr_kom",
        C,
        "de",
        "Das Komitee ist der Ansicht, dass das geltende Raumplanungsgesetz das Wachstum der Siedlungsfläche wirksam stoppt.",
        [
            (
                13,
                "La loi sur l’aménagement du territoire actuelle n’empêche pas l’étalement urbain et sacrifie ainsi des espaces verts.",
            )
        ],
    ),
    (
        "ho-020",
        "Z_fr_kom",
        N,
        "fr",
        "Le comité estime que l’initiative permettrait de créer 20 000 logements supplémentaires dans des quartiers durables.",
        [],
    ),
    # ---------- 2019-02-10, IT booklet ----------
    (
        "ho-021",
        "Z_it_kurz",
        E,
        "it",
        "Secondo il riassunto, l’iniziativa vuole congelare la superficie complessiva delle zone edificabili in Svizzera.",
        [
            (
                4,
                "Il suo obiettivo è congelare la superficie complessiva delle zone edificabili in Svizzera e ammettere nuove zone edificabili soltanto a condizione che altrove una superficie di dimensioni almeno equivalenti sia tolta dalla zona edificabile.",
            )
        ],
    ),
    (
        "ho-022",
        "Z_it_kurz",
        C,
        "fr",
        "Selon le résumé, l’initiative populaire a été déposée en 2013 par les Jeunes Vert’libéraux.",
        [
            (
                4,
                "Nel 2016 i Giovani Verdi hanno depositato l’iniziativa popolare «Fermare la dispersione degli insediamenti – per uno sviluppo insediativo sostenibile (Iniziativa contro la dispersione degli insediamenti)».",
            )
        ],
    ),
    (
        "ho-023",
        "Z_it_kurz",
        N,
        "de",
        "Laut der Zusammenfassung unterstützen mehrere Umweltverbände die Initiative finanziell.",
        [],
    ),
    (
        "ho-024",
        "Z_it_forder",
        E,
        "de",
        "Wird die Initiative angenommen, dürfen landwirtschaftliche Bauten ausserhalb der Bauzonen nur noch bewilligt werden, wenn sie einen direkten Bezug zur Bewirtschaftung des Bodens haben.",
        [
            (
                9,
                "L’iniziativa si propone di limitare ulteriormente la tipologia di edifici e impianti realizzabili al di fuori delle zone edificabili e di ammettere edifici ad uso agricolo soltanto se hanno un nesso diretto con lo sfruttamento del suolo",
            )
        ],
    ),
    (
        "ho-025",
        "Z_it_forder",
        C,
        "fr",
        "Selon le texte, l’initiative gèlerait la surface des zones à bâtir pour une durée limitée à dix ans.",
        [
            (
                9,
                "Essa si propone di congelare la superficie complessiva delle zone edificabili in Svizzera al livello attuale e a tempo indeterminato.",
            )
        ],
    ),
    (
        "ho-026",
        "Z_it_attu",
        N,
        "it",
        "Se l’iniziativa viene accettata, i Cantoni dovranno pubblicare ogni anno un rapporto sull’evoluzione delle zone edificabili.",
        [],
    ),
    (
        "ho-027",
        "Z_it_cf",
        E,
        "fr",
        "Selon le Conseil fédéral, l’initiative nuit à l’agriculture, car dans la plupart des cas des serres ou des halles d’élevage de volaille ne pourraient plus être construites sur des terres agricoles.",
        [
            (15, "L’iniziativa nuoce all’agricoltura."),
            (
                15,
                "Nella maggior parte dei casi, fabbricati quali serre o capannoni per l’allevamento di pollame non potrebbero più essere edificati su terreni agricoli.",
            ),
        ],
    ),
    (
        "ho-028",
        "Z_it_cf",
        C,
        "it",
        "Il Consiglio federale ritiene che l’iniziativa rafforzi il federalismo, ampliando il margine di manovra di Comuni e Cantoni.",
        [
            (
                15,
                "L’iniziativa è in contrasto con il federalismo: congelare le zone edificabili equivale di fatto a limitare il margine di manovra di Comuni e Cantoni.",
            )
        ],
    ),
    (
        "ho-029",
        "Z_it_cf",
        N,
        "fr",
        "Le Conseil fédéral estime que l’initiative ferait renoncer environ 300 entreprises étrangères par an à s’implanter en Suisse.",
        [],
    ),
    (
        "ho-030",
        "Z_it_kom",
        C,
        "de",
        "Laut dem Komitee wird in der Schweiz pro Tag eine Grünfläche von der Grösse von zwei Fussballfeldern überbaut.",
        [
            (
                12,
                "Ogni giorno, in Svizzera, il cemento invade un’area verde grande quanto otto campi di calcio.",
            )
        ],
    ),
    # ---------- 2019-05-19, DE booklet ----------
    (
        "ho-031",
        "S_de_kurz",
        E,
        "de",
        "Laut der Zusammenfassung erhält die AHV pro Jahr rund 2 Milliarden Franken zusätzlich.",
        [
            (
                4,
                "Gleichzeitig erhält die AHV pro Jahr rund 2 Milliarden Franken zusätzlich als Beitrag zur Sicherung der Renten.",
            )
        ],
    ),
    (
        "ho-032",
        "S_de_tab",
        C,
        "fr",
        "Selon les explications, les déductions salariales AVS des employés augmenteront de 0,5 point.",
        [
            (
                15,
                "Für Arbeitnehmerinnen und Arbeitnehmer bedeutet das eine Erhöhung der Lohnabzüge um 0,15 Prozentpunkte",
            )
        ],
    ),
    (
        "ho-033",
        "S_de_detail",
        N,
        "it",
        "Secondo le spiegazioni, la riforma creerà circa 20 000 nuovi posti di lavoro nel settore della ricerca entro il 2025.",
        [],
    ),
    (
        "ho-034",
        "S_de_detail",
        E,
        "fr",
        "Selon les explications, les sociétés dites à statut spécial emploient environ 150 000 personnes en Suisse.",
        [
            (
                10,
                "Diese sogenannten Statusgesellschaften beschäftigen in der Schweiz rund 150 000 Angestellte",
            )
        ],
    ),
    (
        "ho-035",
        "S_de_kom",
        N,
        "de",
        "Das Referendumskomitee ist der Ansicht, dass die STAF zur Schliessung von mindestens 50 Kinderkrippen führen würde.",
        [],
    ),
    (
        "ho-036",
        "W_de_massn",
        E,
        "it",
        "Secondo le spiegazioni, i commercianti dovranno notificare elettronicamente all’ufficio cantonale delle armi tutte le compravendite di armi e di loro parti.",
        [
            (
                37,
                "Händler müssen alle Käufe und Verkäufe von Waffen und Bestandteilen dem kantonalen Waffenbüro elektronisch melden.",
            )
        ],
    ),
    (
        "ho-037",
        "W_de_semi",
        C,
        "de",
        "Laut den Erläuterungen müssen Personen, die bereits eine halbautomatische Waffe mit grossem Magazin besitzen, diese innerhalb von drei Jahren abgeben.",
        [
            (38, "Wer bereits eine solche Waffe besitzt, kann sie behalten."),
            (
                38,
                "Er oder sie muss die Waffe aber innerhalb von drei Jahren beim kantonalen Waffenbüro melden – falls sie dort nicht schon registriert ist.",
            ),
        ],
    ),
    (
        "ho-038",
        "W_de_semi",
        N,
        "fr",
        "Selon les explications, les nouvelles autorisations exceptionnelles seront délivrées pour une durée de dix ans.",
        [],
    ),
    (
        "ho-039",
        "W_de_br",
        C,
        "it",
        "Il Consiglio federale ritiene che la revisione parziale della legge sulle armi disarmerà numerosi tiratori.",
        [(44, "Niemand wird entwaffnet.")],
    ),
    (
        "ho-040",
        "W_de_br",
        N,
        "fr",
        "Le Conseil fédéral estime que la révision partielle réduira de moitié le nombre d’armes illégales en circulation en Suisse.",
        [],
    ),
    # ---------- 2019-05-19, FR booklet ----------
    (
        "ho-041",
        "S_fr_kurz",
        E,
        "fr",
        "Selon le résumé, les privilèges fiscaux accordés aux entreprises actives surtout à l’échelle internationale seront supprimés.",
        [
            (
                4,
                "Les privilèges fiscaux accordés aux entreprises actives surtout à l’échelle internationale seront supprimés.",
            )
        ],
    ),
    (
        "ho-042",
        "S_fr_detail",
        C,
        "de",
        "Laut den Erläuterungen führt die Vorlage bei der direkten Bundessteuer neue Steuererleichterungen für innovative Unternehmen ein.",
        [
            (
                10,
                "Aucun allègement n’est introduit dans le domaine de l’impôt fédéral direct.",
            )
        ],
    ),
    (
        "ho-043",
        "S_fr_detail",
        N,
        "it",
        "Secondo le spiegazioni, la maggior parte dei Cantoni ridurrà l’aliquota dell’imposta sull’utile al 12 per cento.",
        [],
    ),
    (
        "ho-044",
        "S_fr_avs",
        E,
        "it",
        "Secondo le spiegazioni, dal 2020 l’AVS riceverà circa 2 miliardi di franchi in più all’anno, di cui circa 800 milioni versati dalla Confederazione.",
        [
            (
                11,
                "Si le projet est accepté, l’AVS recevra quelque 2 milliards de francs de plus par an à partir de 2020",
            ),
            (
                11,
                "Environ 800 millions de francs seront versés par la Confédération, et le reste sera financé par les entreprises et les assurés",
            ),
        ],
    ),
    (
        "ho-045",
        "S_fr_cf",
        C,
        "it",
        "Il Consiglio federale ritiene che, con il nuovo sistema, le PMI pagheranno complessivamente più imposte di oggi.",
        [
            (
                18,
                "Quant aux autres entreprises, en particulier les PME, elles paieront globalement moins d’impôts en raison des réductions fiscales prévues par la plupart des cantons.",
            )
        ],
    ),
    (
        "ho-046",
        "W_fr_semi",
        E,
        "de",
        "Laut den Erläuterungen wird es kein zentrales Waffenregister geben.",
        [(38, "Il n’y aura pas de registre central des armes.")],
    ),
    (
        "ho-047",
        "W_fr_ctx",
        N,
        "de",
        "Laut den Erläuterungen haben bisher zwölf EU-Staaten die geänderte Waffenrichtlinie vollständig umgesetzt.",
        [],
    ),
    (
        "ho-048",
        "W_fr_trad",
        C,
        "fr",
        "Selon les explications, la Suisse n’a pas pu empêcher que la directive interdise totalement la possession d’armes semi-automatiques par des particuliers.",
        [
            (
                39,
                "Lors de l’élaboration de la modification de la directive de l’UE sur les armes, il a été question entre autres d’interdire totalement la possession d’armes automatiques ou semi-automatiques par des particuliers ou de limiter le nombre d’armes pouvant être détenues.",
            ),
            (
                39,
                "La Suisse est parvenue à empêcher, avec d’autres États, que la directive n’impose des obligations aussi contraignantes.",
            ),
        ],
    ),
    (
        "ho-049",
        "W_fr_cf",
        E,
        "it",
        "Il Consiglio federale ritiene che non si possa parlare di un diktat dell’UE, poiché la Svizzera ha potuto partecipare all’elaborazione della modifica della direttiva.",
        [
            (
                44,
                "La Suisse participant au système Schengen, elle a pu prendre part à l’élaboration de la modification de la directive.",
            ),
            (44, "On ne peut donc pas parler de « diktat de l’UE »."),
        ],
    ),
    (
        "ho-050",
        "W_fr_cf",
        N,
        "fr",
        "Le Conseil fédéral estime que la révision partielle permettra d’économiser 40 millions de francs par an dans le domaine de l’asile.",
        [],
    ),
    # ---------- 2019-05-19, IT booklet ----------
    (
        "ho-051",
        "S_it_kurz",
        E,
        "it",
        "Secondo il riassunto, molti Cantoni intendono abbassare le imposte sulle imprese, ma queste riduzioni non fanno parte del progetto.",
        [
            (
                4,
                "Molti Cantoni intendono abbassare le imposte sulle imprese per restare attrattivi.",
            ),
            (
                4,
                "Queste riduzioni di imposta, benché correlate, non fanno parte del presente progetto.",
            ),
        ],
    ),
    (
        "ho-052",
        "S_it_tab",
        C,
        "fr",
        "Selon les explications, la Confédération versera environ 1,2 milliard de francs à l’AVS, le reste étant financé par les entreprises et les assurés.",
        [
            (15, "800 milioni circa proverranno dalla Cassa federale"),
            (
                15,
                "Le imprese e gli assicurati contribuiranno con 1,2 miliardi di franchi",
            ),
        ],
    ),
    (
        "ho-053",
        "S_it_tab",
        N,
        "de",
        "Laut den Erläuterungen wird die Zusatzfinanzierung der AHV nach zehn Jahren automatisch überprüft.",
        [],
    ),
    (
        "ho-054",
        "S_it_cf",
        E,
        "fr",
        "Selon le Conseil fédéral, les sociétés qui bénéficient actuellement de privilèges seront dans l’ensemble imposées plus fortement.",
        [
            (
                18,
                "Vi sarà complessivamente un aumento delle imposte per le società che beneficiano attualmente di privilegi.",
            )
        ],
    ),
    (
        "ho-055",
        "S_it_cf",
        C,
        "it",
        "Secondo il Consiglio federale, senza l’abolizione dei privilegi fiscali la Svizzera non dovrebbe temere contromisure da parte di altri Paesi.",
        [
            (
                19,
                "Senza l’abolizione dei privilegi fiscali la Svizzera dovrebbe aspettarsi da parte degli altri Paesi l’adozione di contromisure, che danneggerebbero la nostra economia.",
            )
        ],
    ),
    (
        "ho-056",
        "W_it_kurz",
        N,
        "it",
        "Secondo il riassunto, la modifica della direttiva UE sulle armi deve essere applicata negli Stati membri dal 1° gennaio 2018.",
        [],
    ),
    (
        "ho-057",
        "W_it_kurz",
        E,
        "de",
        "Laut der Zusammenfassung können Sturmgewehre weiterhin direkt von der Armee übernommen werden.",
        [
            (
                6,
                "I fucili d’assalto possono tuttavia continuare a essere acquisiti in proprietà direttamente dall’esercito.",
            )
        ],
    ),
    (
        "ho-058",
        "W_it_semi",
        C,
        "it",
        "Secondo le spiegazioni, chi acquista un’arma dovrà sottoporsi a test medici e psicologici.",
        [
            (
                38,
                "Non sono introdotti test medici e psicologici, né un obbligo di aderire a una società di tiro se si intende acquistare un’arma.",
            )
        ],
    ),
    (
        "ho-059",
        "W_it_trad",
        N,
        "fr",
        "Selon les explications, la Fête fédérale de tir réunit chaque fois plus de 30 000 tireurs.",
        [],
    ),
    (
        "ho-060",
        "W_it_cf",
        C,
        "de",
        "Der Bundesrat ist der Ansicht, dass ein Nein zur Vorlage die Zusammenarbeit mit den Schengen- und Dublin-Staaten nicht gefährden würde.",
        [
            (
                45,
                "Un no metterebbe automaticamente fine a questa collaborazione, poiché non è plausibile che tutti gli Stati membri dell’UE e la Commissione europea vengano incontro alla Svizzera entro il breve termine previsto.",
            )
        ],
    ),
    # ---------- 2018-06-10, DE booklet ----------
    (
        "ho-061",
        "V_de_br",
        E,
        "de",
        "Der Bundesrat spricht sich dafür aus, die Vollgeld-Initiative abzulehnen.",
        [
            (
                15,
                "Aus all diesen Gründen empfehlen Bundesrat und Parlament, die Volksinitiative «Für krisensicheres Geld: Geldschöpfung allein durch die Nationalbank! (Vollgeld-Initiative)» abzulehnen.",
            )
        ],
    ),
    (
        "ho-062",
        "V_de_p7",
        C,
        "fr",
        "Selon les explications, le secteur financier représente 9,1 % de l’ensemble des emplois en Suisse.",
        [
            (
                7,
                "Er macht 5,6 Prozent der Gesamtbeschäftigung der Schweiz aus und hat einen Wertschöpfungsanteil von 9,1 Prozent am Bruttoinlandprodukt.",
            )
        ],
    ),
    (
        "ho-063",
        "V_de_p7",
        N,
        "it",
        "Secondo le spiegazioni, in caso di accettazione dell’iniziativa la BNS dovrebbe distribuire a ogni abitante almeno 1000 franchi all’anno.",
        [],
    ),
    (
        "ho-064",
        "V_de_kurz",
        E,
        "it",
        "Secondo il riassunto, i promotori dell’iniziativa vedono nella creazione di moneta da parte delle banche una causa essenziale delle crisi finanziarie.",
        [
            (
                5,
                "Die Initiantinnen und Initianten sehen in der Geldschöpfung durch die Banken eine wesentliche Ursache von Finanzkrisen.",
            )
        ],
    ),
    (
        "ho-065",
        "V_de_kom",
        C,
        "de",
        "Das Komitee ist der Ansicht, dass heute nur rund 10 Prozent des zirkulierenden Geldes virtuelles Buchgeld der Banken sind.",
        [
            (
                13,
                "Doch heute zirkuliert zu 90 % virtuelles Buchgeld, das die Banken selbst erzeugen.",
            )
        ],
    ),
    (
        "ho-066",
        "G_de_kurz",
        N,
        "fr",
        "Selon le résumé, la nouvelle loi autorise l’ouverture de cinq nouvelles maisons de jeu en Suisse.",
        [],
    ),
    (
        "ho-067",
        "G_de_detail",
        E,
        "fr",
        "Selon les explications, les gains de loterie seront exonérés d’impôt jusqu’à un million de francs.",
        [
            (
                19,
                "So werden zum Beispiel alle Lotteriegewinne bis zu einer Million Franken steuerfrei sein.",
            )
        ],
    ),
    (
        "ho-068",
        "G_de_br",
        C,
        "it",
        "Il Consiglio federale ritiene che il blocco dei giochi in linea non autorizzati limiti la libertà di opinione e d’informazione.",
        [
            (
                25,
                "Meinungs‑ und Informationsfreiheit werden in keiner Weise eingeschränkt.",
            )
        ],
    ),
    (
        "ho-069",
        "G_de_kom",
        N,
        "de",
        "Das Referendumskomitee ist der Ansicht, dass Netzsperren den Internet-Providern jährliche Kosten von über 20 Millionen Franken verursachen.",
        [],
    ),
    (
        "ho-070",
        "G_de_detail",
        C,
        "it",
        "Secondo le spiegazioni, l’articolo costituzionale sui giochi in denaro è stato accettato nel marzo 2012 dal 57 per cento dei votanti.",
        [
            (
                18,
                "Dieser Artikel wurde im März 2012 von 87 Prozent der Stimmenden und von allen Kantonen angenommen.",
            )
        ],
    ),
    # ---------- 2018-06-10, FR booklet ----------
    (
        "ho-071",
        "V_fr_cf",
        E,
        "fr",
        "Selon le Conseil fédéral, la protection des déposants couvre désormais 100 000 francs par client et par banque en cas de faillite.",
        [
            (
                14,
                "La protection des déposants a elle aussi été renforcée, un montant de 100 000 francs par client et par banque étant désormais couvert en cas de faillite.",
            )
        ],
    ),
    (
        "ho-072",
        "V_fr_cf",
        N,
        "fr",
        "Le Conseil fédéral estime que l’initiative entraînerait la suppression d’environ 10 000 emplois dans le secteur bancaire.",
        [],
    ),
    (
        "ho-073",
        "V_fr_cf",
        C,
        "de",
        "Laut dem Bundesrat wurde das von der Initiative vorgeschlagene System bereits in mehreren Ländern erfolgreich umgesetzt.",
        [(15, "Aucun autre pays ne pratique le système proposé par l’initiative.")],
    ),
    (
        "ho-074",
        "V_fr_kom",
        E,
        "it",
        "Secondo il comitato d’iniziativa, il popolo ha attribuito già nel 1891 alla Banca nazionale il diritto esclusivo di emettere banconote.",
        [
            (
                13,
                "Le peuple a remis le droit exclusif d’émettre des billets de banque à la Banque nationale en 1891 déjà.",
            )
        ],
    ),
    (
        "ho-075",
        "V_fr_kom",
        N,
        "de",
        "Das Komitee ist der Ansicht, dass die Vollgeld-Initiative die Hypothekarzinsen langfristig senken würde.",
        [],
    ),
    (
        "ho-076",
        "G_fr_detail",
        E,
        "de",
        "Laut den Erläuterungen ersetzt das neue Gesetz das Spielbankengesetz von 1998 und das Lotteriegesetz von 1923.",
        [
            (
                18,
                "Cette loi remplace la loi de 1998 sur les maisons de jeu et la loi de 1923 sur les loteries.",
            )
        ],
    ),
    (
        "ho-077",
        "G_fr_kom",
        C,
        "it",
        "Secondo il comitato referendario, il referendum mette a rischio le risorse del fondo delle lotterie destinate allo sport e alla cultura.",
        [
            (
                23,
                "Les ressources du Fonds de loterie destinées au sport et à la culture ne sont pas affectées par le référendum.",
            )
        ],
    ),
    (
        "ho-078",
        "G_fr_box",
        N,
        "it",
        "Secondo le spiegazioni, gli utenti che aggirano il blocco d’accesso rischiano una multa fino a 10 000 franchi.",
        [],
    ),
    (
        "ho-079",
        "G_fr_cf",
        C,
        "fr",
        "Selon le Conseil fédéral, la Suisse sera le premier pays européen à bloquer l’accès aux jeux en ligne non autorisés.",
        [
            (
                25,
                "La loi fédérale sur les jeux d’argent prévoit donc que la Suisse, comme 17 autres pays européens, bloquera l’accès aux jeux en ligne non autorisés",
            )
        ],
    ),
    (
        "ho-080",
        "G_fr_kurz",
        N,
        "fr",
        "Selon le résumé, le référendum contre la loi a été déposé avec plus de 60 000 signatures.",
        [],
    ),
    # ---------- 2018-06-10, IT booklet ----------
    (
        "ho-081",
        "V_it_cf",
        E,
        "it",
        "Il Consiglio federale consiglia di respingere l’iniziativa Moneta intera.",
        [
            (
                15,
                "Per tutte queste ragioni, Consiglio federale e Parlamento raccomandano di respingere l’iniziativa popolare «Per soldi a prova di crisi: emissione di moneta riservata alla Banca nazionale! (Iniziativa Moneta intera)».",
            )
        ],
    ),
    (
        "ho-082",
        "V_it_p4",
        C,
        "de",
        "Laut den Erläuterungen hat der Nationalrat die Vollgeld-Initiative mit 169 zu 9 Stimmen angenommen.",
        [
            (
                4,
                "Il Consiglio nazionale ha respinto l’iniziativa con 169 voti contro 9 e 12 astensioni, il Consiglio degli Stati con 42 voti contro 0 e 1 astensione.",
            )
        ],
    ),
    (
        "ho-083",
        "V_it_kom",
        N,
        "fr",
        "Selon le comité d’initiative, la Banque nationale ramènerait ses taux d’intérêt à zéro dès l’introduction de la monnaie pleine.",
        [],
    ),
    (
        "ho-084",
        "V_it_cf",
        E,
        "de",
        "Der Bundesrat vertritt die Auffassung, dass eine direkte Finanzierung von Staatsausgaben durch die SNB in der Regel zu Inflation führt und heute verboten ist.",
        [
            (
                15,
                "Ciò non solo comporta grandi rischi, ma è anche attualmente vietato dalla legge, poiché di norma si traduce in una svalutazione monetaria (inflazione).",
            )
        ],
    ),
    (
        "ho-085",
        "V_it_kurz",
        C,
        "fr",
        "Selon le résumé, l’initiative permettrait aux banques commerciales de continuer à créer de l’argent en accordant des crédits.",
        [
            (
                5,
                "Ne consegue che le banche commerciali non potrebbero più emettere moneta mediante la concessione di crediti.",
            )
        ],
    ),
    (
        "ho-086",
        "G_it_cf",
        E,
        "de",
        "Laut dem Bundesrat gehen jedes Jahr fast eine Milliarde Franken aus legalen Geldspielen an die AHV/IV und an gemeinnützige Organisationen.",
        [
            (
                24,
                "ogni anno quasi un miliardo di franchi è infatti destinato all’AVS/AI come pure – attraverso i fondi cantonali delle lotterie – a un gran numero di organizzazioni di utilità pubblica.",
            )
        ],
    ),
    (
        "ho-087",
        "G_it_cf",
        N,
        "it",
        "Secondo il Consiglio federale, Swisslos verserà ogni anno 50 milioni di franchi supplementari al Museo svizzero dei trasporti.",
        [],
    ),
    (
        "ho-088",
        "G_it_kom",
        C,
        "it",
        "Secondo il comitato referendario, il Parlamento e i casinò hanno accolto le principali richieste delle associazioni per la protezione dei giocatori.",
        [
            (
                23,
                "il Parlamento e i casinò hanno respinto le principali rivendicazioni delle associazioni per la protezione dei giocatori, ovvero l’introduzione di una tassa per la prevenzione e l’istituzione di una commissione peritale consultiva.",
            )
        ],
    ),
    (
        "ho-089",
        "G_it_detail",
        N,
        "de",
        "Laut den Erläuterungen dürfen an kleinen Pokerturnieren ausserhalb von Spielbanken höchstens zehn Personen teilnehmen.",
        [],
    ),
    (
        "ho-090",
        "G_it_detail",
        E,
        "fr",
        "Selon les explications, les autorités de surveillance devront compter au moins un spécialiste de la prévention des addictions parmi leurs dirigeants.",
        [
            (
                19,
                "fra i loro dirigenti devono contare almeno uno specialista di prevenzione delle dipendenze.",
            )
        ],
    ),
]
