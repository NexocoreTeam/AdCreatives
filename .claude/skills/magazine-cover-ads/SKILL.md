---
name: magazine-cover-ads
description: Make static ads, carousel first cards or video opening frames that hit like a magazine cover, by borrowing one cover move per ad (a visual joke, a nearly empty page, a giant numeral, one huge blunt word, an "issue" cover, an instruction on the product). Use when the user asks for "magazine cover style", "cover-style ads", "editorial style", "Bloomberg style", "like a magazine cover", "the magazine style" or "the magazine test", or wants ads that do not look like the usual e-commerce ad. Most moves are built locally from the client's own product photos with flat colour and type, so they need no paid generation.
metadata:
  version: 1.0.0
---

# Magazine Cover Ads

The first frame of an ad is a cover. A static, the first card of a carousel and the opening frame of a video all
have a cover's one job: make someone stop. Magazines have practised that job for a century, so their covers are
the best reference there is for it.

This skill turns that idea into ads. Each ad borrows one **move** from great covers. A move is an idea or a
layout. It is never a cover's own artwork, words, colours or masthead.

## When to use it

- The user asks for magazine-cover, cover-style or editorial-style ads, or names this skill.
- The user wants something that does not look like every other product ad, and the brand can carry a bold look.
- A carousel or a video needs a stronger first frame.

Do not use it to override a client's approved look without saying so. Read the client's
`creative-preferences.md` first. If the cover style breaks that look, offer it as an experiment and label the
files as a test.

## Before you build

1. **Pick the product and collect its facts.** Sizes, counts, what it turns into, what is on sale. Every claim
   comes from the product page. The best cover ideas are a product fact shown in a surprising way.
2. **Pick three to six moves** from the list below that suit the facts.
3. **Propose one line per ad** unless the user asked you to just make a set (the `creative-variant-explorer`
   skill). Say which facts each one uses.

## The moves

| Move | What it looks like | Works when |
|---|---|---|
| One visual joke, small headline | The product does one absurd, true thing: too long for the page, too small to find. A small headline and a three-line deck sit in a corner | The product has one striking dimension or count |
| The nearly empty page | A flat field, the product small, a few words low on the right. The emptiness is the message | The benefit is space, calm, time or less of something |
| A giant numeral or word as the picture | One number or word fills the page. The product stands in front of it | One number sells the product: seats, hours, sizes |
| A small line, then one huge blunt word | A quiet first line, then a word as tall as a third of the page, over a full photo. A boxed line below resolves it | There is a provocation the product answers |
| The "issue" cover | The brand's logo as the masthead, a row of numbered teasers, a framed photo, a colour band with the "cover story" | The product has three or more facts worth a line each |
| One instruction on the product | A large circle or arrow on the product that tells the viewer what to do: pull, lift, turn | The product changes when you do one thing to it |
| A pastiche of a printed thing | The ad borrows the look of a ticket, a label, a classified or a sale flyer | A sale or an offer needs a fresh frame. Imitate a kind of object, never a real brand's |
| A fact as the picture | One true number or a simple chart is the artwork | There is a comparison that is true and sourced |
| Type that misbehaves | Words run off the page, stack, warp or get cut by the product | The line is short and strong enough to survive it |
| One image in a white frame | A single striking picture, a wide margin, the wordmark large at the bottom | There is one very good photo |

Small parts that make a page read as a cover: a ticker line of repeated words along the top and bottom, a logo
kept small like a masthead, two or three flat colours, and a wide gap between the biggest and smallest type.

## How to build one

Most of these are local work: Pillow for layout, FFmpeg only if it moves. Nothing is generated.

1. **Size.** Build 4:5 (1080 x 1350) first. Make 9:16 only for the ones the user keeps.
2. **Product.** Use the client's own photos. For a cut-out:
   - a dark or coloured product on pure white: every near-white pixel is backdrop, also between the legs;
   - a wood or coloured product on a grey studio backdrop: OpenCV GrabCut, started from colour (colourless
     pixels as likely backdrop, coloured ones as likely product, the picture's edge as backdrop for sure);
   - then feather the edge by about a pixel and add a soft dark ellipse on the floor under it.
   Look at every cut-out on a strong colour before using it. A white product on white, hair, glass and thin
   wires need a proper mask or a generated one: say so instead of shipping a rough edge.
3. **Never distort the product.** Crop it, scale it, let it run off the page. Do not stretch it or redraw it.
4. **Colour.** One flat field per ad, two or three colours in all. Take one from the brand. Do not reuse the
   colours of the cover you learned the move from.
5. **Type.** One blunt sans and one serif are enough. Use the client's own faces when there are any, and skip a
   face the client has turned down. Make the big type very big and the small type small.
6. **Words.** One idea per ad. A headline of two to five words, and a deck of at most three short lines. True,
   simple enough for a child to read, no em-dashes. The joke is in the fact, not in wordplay.
7. **Brand.** The logo sits small, like a masthead. No real magazine's name, masthead or layout is imitated, and
   there are no made-up barcodes, issue prices or dates that could pass as real.

## Check before showing

- The product's shape and proportions are right, and no words cover it.
- Every number and claim is on the product page, for the market the ad is for.
- The words can be read at phone size: check the smallest line.
- The cut-out has no halo and no missing parts at full size.
- It is labelled as a test if the client has not approved this look.

## What it costs

Nothing for the moves above. A drawn or painted cover, in the manner of an illustrated magazine, needs generated
art: quote it and get a go first, as for any paid generation.

## Where the idea comes from

A creative director's short video on magazine references for social media: the first panel of a carousel is a
cover and should hit like one. A first test in November 2026 built six of these moves in one sitting from a
client's product photos, with no generation. The cut-outs were the slow part. See also
`docs/inspiration-sources.md`.
