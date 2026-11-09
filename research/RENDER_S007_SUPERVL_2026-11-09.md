# RENDER shot 7 rework pre-flight, Super VL NVIDIA (prompt + 2 pictures) 11-09 12:28

HIGH | "On the left, Sandhya draws her veil close and turns her face away, gaze lowered;" | Picture B shows Sandhya facing forward with eyes open, looking toward Kamadeva, not face away or gaze lowered; this will mismatch the required last frame. | Change to: Sandhya draws her veil close and watches Kamadeva with eyes open.

HIGH | "the bees on the string hum louder." | No bees appear on the bowstring in Picture A or B; the word can make the model render bees that are not in the references. | Delete the clause or move it to the sound-effects-only soundscape line.

HIGH | "the figure's mouth stays closed except for non-verbal breaths at second 2. Silent performance: the figure never speaks, and his mouth stays shut while his lips remain completely closed for the whole shot." | Contradictory instructions: permits mouth opening at second 2, then demands lips completely closed for the whole shot; confuses frame-level mouth animation. | Remove the exception: keep only "his lips remain completely closed for the whole shot."

LOW | "Release: the flower arrow leaps across the court with a bright trail;" | Picture B shows no bright arrow trail at the end mark; a lingering trail would clash with the required final frame. | Specify the trail clears before the 8.71-second end frame.