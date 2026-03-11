"""Anchor-based rubric definitions per dimension for judge prompt."""

CLARITY_ANCHORS = """Clarity anchors:
  Low (1-4): "Our experienced tutors are ready to help with all your academic needs" — vague, no specific claim.
  Medium (5-7): "Get expert SAT prep from certified tutors" — clear category but generic benefit.
  High (8-10): "Your daughter could score 200+ points higher in 8 weeks" — specific, quantified."""

VALUE_PROP_ANCHORS = """Value Proposition anchors:
  Low (1-4): "We have experienced tutors available for SAT prep" — feature-focused, no outcome.
  Medium (5-7): "Varsity Tutors offers personalized SAT prep programs" — mentions personalization, no proof.
  High (8-10): "Students who prep with Varsity Tutors average 193-point SAT improvements" — specific outcome."""

CTA_ANCHORS = """CTA anchors:
  Low (1-4): "Learn more" with no context, or no CTA.
  Medium (5-7): "Start your SAT prep today" — specific but low urgency.
  High (8-10): "Get your free SAT score analysis — test is in 6 weeks" — specific action, urgency."""

BRAND_VOICE_ANCHORS = """Brand Voice anchors:
  Low (1-4): "Get better test scores with our affordable tutoring" — generic, transactional.
  Medium (5-7): "Personalized SAT prep that fits your schedule and goals" — approachable.
  High (8-10): "You already have what it takes — let's unlock your best SAT score" — empowering."""

EMOTIONAL_RESONANCE_ANCHORS = """Emotional Resonance anchors (parent frame):
  Low (1-4): "SAT prep courses available for your student"
  Medium (5-7): "Worried about your child's SAT score? We can help"
  High (8-10): "Application deadlines don't wait. Neither should your student's score."
Student frame:
  Low (1-4): "Study for the SAT with our expert tutors"
  Medium (5-7): "Stressed about the SAT? You're not alone"
  High (8-10): "Everyone else is already prepping. Where are you starting?" """


def get_rubric_block() -> str:
    """Full rubric text for judge prompt."""
    return "\n\n".join([
        CLARITY_ANCHORS,
        VALUE_PROP_ANCHORS,
        CTA_ANCHORS,
        BRAND_VOICE_ANCHORS,
        EMOTIONAL_RESONANCE_ANCHORS,
    ])
