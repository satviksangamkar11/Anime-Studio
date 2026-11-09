# RENDER shot 9 rework pre-flight, Super VL NVIDIA (prompt + 2 pictures) 11-09 10:59

HIGH | "Shiva stands calm and still at the far left with his trident, eyes closed." | Both reference pictures show Shiva with open eyes; this will alter a visible feature in frames A and B. | Change to "eyes open" or delete "eyes closed".

HIGH | "Kamadeva hurriedly gathers his arrows to his chest, eyes wide;" | Picture A shows Kamadeva holding his bow down at his side, not gathering arrows to his chest; contradicts the first frame. | Change to "Kamadeva holds his bow at his side, eyes wide".

HIGH | "Kamadeva's bow slips under his arm; his hands tremble," | Picture B shows Kamadeva holding the bow by the grip at his side, not slipped under his arm; contradicts the last frame. | Change to "Kamadeva holds his bow at his side".

HIGH | "The figure's mouth stays closed except for non-verbal breaths at seconds 5 and 7. Silent performance: the figure never speaks, and his mouth stays shut while his lips remain completely closed for the whole shot." | Direct contradiction (closed except breaths vs completely closed whole shot) and ambiguous "the figure" among three characters; will confuse the model. | Specify one figure and remove the exception: "Brahma's mouth stays shut and lips remain completely closed for the whole shot."

HIGH | "devas_neon palette colours" | Reference pictures use a warm gold/cel palette, not neon; this term may inject out-of-scope colors. | Change to "devas warm gold palette colours" or delete "neon".

MEDIUM | "one finger pointed at Kamadeva" | Picture A shows Brahma's raised hand holding a gesture/object, not clearly pointing a finger at Kamadeva; may create a mismatched opening pose. | Change to "one hand raised toward Kamadeva" to match Picture A.

LOW | none