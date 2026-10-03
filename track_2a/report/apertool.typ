#let report(
  title: "",
  subtitle: "",
  track: "",
  authors: (),
  abstract: none,
  apertus: none,
  links: (),
  body,
) = {
  set document(title: title, author: authors.map(a => a.name))
  set page(
    paper: "a4",
    margin: (x: 1.8cm, top: 2cm, bottom: 2cm),
    columns: 2,
    numbering: "1",
    header: context {
      if counter(page).get().first() > 1 [
        #set text(8pt, fill: luma(110))
        #title #h(1fr) Apertool · Hack Apertus 2026 · #track
      ]
    },
  )
  set columns(gutter: 0.6cm)
  set text(font: "Libertinus Serif", size: 10pt, lang: "en")
  set par(justify: true, leading: 0.55em, spacing: 0.9em)
  show heading.where(level: 1): set text(11pt)
  show heading.where(level: 2): set text(10pt)
  show heading: set block(above: 1.1em, below: 0.6em)
  set figure(gap: 0.5em)
  show figure.caption: set text(8.5pt)
  set table(stroke: none, inset: (x: 4pt, y: 3pt))
  show table: set text(8.5pt)
  show raw: set text(font: "DejaVu Sans Mono", size: 8pt)
  show link: set text(fill: rgb("#1a4f8b"))
  set bibliography(title: none)

  place(top + center, scope: "parent", float: true, {
    align(center)[
      #text(16pt, weight: "bold", title)
      #if subtitle != "" [ \ #text(11pt, subtitle) ]
      #v(0.4em)
      #text(10pt, authors.map(a => a.name + if "affiliation" in a [ (#a.affiliation)]).join(", "))
      \ #text(9pt, fill: luma(80))[Team Apertool · Hack Apertus 2026 · #track]
      #if links.len() > 0 [ \ #text(8.5pt, links.map(l => link(l.url, l.label)).join(" · ")) ]
    ]
    v(0.6em)
    if abstract != none {
      block(width: 100%, inset: (x: 1.2cm), {
        set par(justify: true)
        text(9pt)[*Abstract.* #abstract]
      })
      v(0.4em)
    }
    if apertus != none { block(width: 100%, inset: (x: 1.2cm), {
      set text(8.5pt)
      table(
        columns: (auto, 1fr),
        align: left,
        [*Model*], apertus.model,
        [*How it is used*], apertus.usage,
        [*Where it runs*], apertus.runs,
      )
    }) }
    v(0.8em)
  })

  body
}
