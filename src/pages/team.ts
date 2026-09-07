const CONTACT_EMAIL = "s2s.scdlds@ashoka.edu.in";

interface TeamMember {
  name: string;
  projectRole: string;
  professionalTitle: string;
  affiliation: string;
  expertise: string;
  image: string;
  imagePosition?: string;
  profile: string;
}

const SCIENTIFIC_TEAM: TeamMember[] = [
  {
    name: "Ayush Raj",
    projectRole: "Lead Researcher",
    professionalTitle: "MS Thesis Researcher · AI weather research",
    affiliation: "IISER Pune · SCDLDS",
    expertise: "AI for weather and climate prediction, with a focus on improving regional S2S forecasts.",
    image: "./team/ayush-raj.webp",
    profile: "https://in.linkedin.com/in/ayush-raj-7608a424a",
  },
  {
    name: "Manmeet Singh",
    projectRole: "Lead Scientist",
    professionalTitle: "Assistant Professor",
    affiliation: "Western Kentucky University · SCDLDS",
    expertise: "AI for climate and disaster science, weather prediction, and Earth system modelling.",
    image: "./team/manmeet-singh.jpg",
    imagePosition: "center 18%",
    profile: "https://www.wku.edu/eeas/staff/manmeet_singh",
  },
  {
    name: "Parthasarathi Mukhopadhyay",
    projectRole: "Senior Scientist",
    professionalTitle: "Visiting Faculty · Earth & Environmental Sciences",
    affiliation: "IISER Berhampur · FASc · SCDLDS",
    expertise: "Numerical weather prediction, monsoon modelling, clouds, and convection.",
    image: "./team/parthasarathi-mukhopadhyay.jpg",
    imagePosition: "center 18%",
    profile: "https://www.iiserbpr.ac.in/people/profile/parthasarathym",
  },
  {
    name: "Sandeep Juneja",
    projectRole: "Principal Investigator",
    professionalTitle: "Professor of Computer Science · Centre Director",
    affiliation: "Ashoka University · SCDLDS",
    expertise: "Applied probability, machine learning, and monsoon weather modelling.",
    image: "./team/sandeep-juneja.jpg",
    profile: "https://www.ashoka.edu.in/profile/sandeep-juneja/",
  },
  {
    name: "Saptarishi Dhanuka",
    projectRole: "Researcher",
    professionalTitle: "Pre-doctoral Fellow · AI weather research",
    affiliation: "Ashoka University · SCDLDS",
    expertise: "Artificial intelligence for weather, climate, and data-driven forecasting.",
    image: "./team/saptarishi-dhanuka.jpg",
    imagePosition: "center 20%",
    profile: "https://www.linkedin.com/in/saptarishi-dhanuka/",
  },
];

function renderMember(member: TeamMember): string {
  const memberId = `team-member-${member.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  const imageStyle = member.imagePosition
    ? ` style="object-position: ${member.imagePosition}"`
    : "";

  return `
    <article class="team-person-card" role="listitem" aria-labelledby="${memberId}">
      <div class="team-person-card__portrait">
        <img src="${member.image}" alt="Portrait of ${member.name}" loading="lazy" decoding="async"${imageStyle} />
      </div>
      <div class="team-person-card__identity">
        <h2 id="${memberId}">${member.name}</h2>
        <p class="team-person-card__role">${member.professionalTitle}</p>
        <p class="team-person-card__affiliation">${member.affiliation}</p>
      </div>
      <p class="team-person-card__project-role">${member.projectRole}</p>
      <div class="team-person-card__details">
        <span class="team-person-card__expertise-label">Research focus</span>
        <p class="team-person-card__expertise">${member.expertise}</p>
      </div>
      <a
        class="team-person-card__profile"
        href="${member.profile}"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Open ${member.name}'s public profile in a new tab"
      >Profile <span aria-hidden="true">↗</span></a>
    </article>
  `;
}

export function renderTeamPage(container: HTMLElement): void {
  container.innerHTML = `
    <section class="team-page" aria-labelledby="team-title">
      <header class="team-hero">
        <span class="team-eyebrow">Research team</span>
        <h1 id="team-title">Research contributors</h1>
        <p class="team-hero__intro">
          Researchers contributing to experimental subseasonal forecasting for India.
        </p>
      </header>

      <section class="team-roster" aria-label="Research contributors" aria-describedby="team-order-note">
        <p class="team-roster__note" id="team-order-note">
          Listed alphabetically by first name.
        </p>
        <div class="team-directory">
          <div class="team-directory__header" aria-hidden="true">
            <span>Researcher</span>
            <span>Project role</span>
            <span>Research focus</span>
            <span>Profile</span>
          </div>
          <div class="team-grid" role="list">
            ${SCIENTIFIC_TEAM.map(renderMember).join("")}
          </div>
        </div>
      </section>

      <section class="team-contact" aria-labelledby="team-contact-title">
        <div class="team-contact__intro">
          <span class="team-contact__eyebrow">Contact us</span>
          <h2 id="team-contact-title">Talk to the research team</h2>
          <p>
            For questions about the forecast, data access, or research
            collaboration, write to the S2S team.
          </p>
        </div>

        <a class="team-contact__email" href="mailto:${CONTACT_EMAIL}">
          <span>Email the team</span>
          <strong>${CONTACT_EMAIL}</strong>
          <span class="team-contact__arrow" aria-hidden="true">→</span>
        </a>

        <div class="team-contact__note">
          <p>
            <strong>Experimental guidance.</strong>
            For research use only—not an operational weather forecast or warning.
          </p>
          <a href="./#briefing">Latest briefing →</a>
        </div>
      </section>
    </section>
  `;
}
