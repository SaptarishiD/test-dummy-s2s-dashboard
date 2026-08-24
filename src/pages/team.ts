const CONTACT_EMAIL = "raj.ayush@students.iiserpune.ac.in";

interface TeamMember {
  name: string;
  role: string;
  affiliation: string;
  expertise: string;
  image: string;
  imagePosition?: string;
  profile: string;
}

const SCIENTIFIC_TEAM: TeamMember[] = [
  {
    name: "Saptarishi Dhanuka",
    role: "Pre-doctoral Fellow · AI weather research",
    affiliation: "Ashoka University · SCDLDS",
    expertise: "Artificial intelligence for weather, climate, and data-driven forecasting.",
    image: "./team/saptarishi-dhanuka.jpg",
    imagePosition: "center 20%",
    profile: "https://www.ashoka.edu.in/profile/saptarishi-dhanuka/",
  },
  {
    name: "Sandeep Juneja",
    role: "Professor of Computer Science · Centre Director",
    affiliation: "Ashoka University · SCDLDS",
    expertise: "Applied probability, machine learning, and monsoon weather modelling.",
    image: "./team/sandeep-juneja.jpg",
    profile: "https://www.ashoka.edu.in/profile/sandeep-juneja/",
  },
  {
    name: "Parthasarathi Mukhopadhyay",
    role: "Visiting Faculty · Earth & Environmental Sciences",
    affiliation: "IISER Berhampur · FASc · SCDLDS",
    expertise: "Numerical weather prediction, monsoon modelling, clouds, and convection.",
    image: "./team/parthasarathi-mukhopadhyay.jpg",
    imagePosition: "center 18%",
    profile: "https://www.iiserbpr.ac.in/people/profile/parthasarathym",
  },
  {
    name: "Ayush Raj",
    role: "MS Thesis Researcher · AI weather research",
    affiliation: "IISER Pune · SCDLDS",
    expertise: "AI subseasonal-to-seasonal prediction, forecast verification, and dashboard development.",
    image: "./team/ayush-raj.webp",
    profile: "https://in.linkedin.com/in/ayush-raj-7608a424a",
  },
  {
    name: "Manmeet Singh",
    role: "Project Lead · Assistant Professor",
    affiliation: "Western Kentucky University · SCDLDS",
    expertise: "AI for climate and disaster science, weather prediction, and Earth system modelling.",
    image: "./team/manmeet-singh.jpg",
    imagePosition: "center 18%",
    profile: "https://www.wku.edu/eeas/staff/manmeet_singh",
  },
];

function renderMember(member: TeamMember): string {
  const imageStyle = member.imagePosition
    ? ` style="object-position: ${member.imagePosition}"`
    : "";

  return `
    <article class="team-person-card">
      <div class="team-person-card__portrait">
        <img src="${member.image}" alt="Portrait of ${member.name}" loading="lazy" decoding="async"${imageStyle} />
      </div>
      <div class="team-person-card__body">
        <h3>${member.name}</h3>
        <p class="team-person-card__role">${member.role}</p>
        <p class="team-person-card__affiliation">${member.affiliation}</p>
        <p class="team-person-card__expertise">${member.expertise}</p>
        <a
          class="team-person-card__profile"
          href="${member.profile}"
          target="_blank"
          rel="noopener noreferrer"
        >Public profile <span aria-hidden="true">↗</span></a>
      </div>
    </article>
  `;
}

export function renderTeamPage(container: HTMLElement): void {
  container.innerHTML = `
    <section class="team-page" aria-labelledby="team-title">
      <header class="team-hero">
        <span class="team-eyebrow">S2S Research · Scientific team</span>
        <h1 id="team-title">People behind the forecast</h1>
        <p class="team-hero__intro">
          Scientists and researchers working across atmospheric science,
          machine learning, forecast verification, and subseasonal guidance.
        </p>
      </header>

      <section class="team-roster" aria-labelledby="team-roster-title">
        <header class="team-section-heading">
          <div>
            <span class="team-eyebrow">Directory</span>
            <h2 id="team-roster-title">Scientific contributors</h2>
          </div>
          <p>Researchers and collaborators are listed alphabetically by surname.</p>
        </header>
        <div class="team-grid">
          ${SCIENTIFIC_TEAM.map(renderMember).join("")}
        </div>
      </section>

      <aside class="team-context" aria-label="Research context and team links">
        <div>
          <span>Research context</span>
          <p>
            The team develops experimental research guidance for scientific
            review, not operational forecasts or warnings.
          </p>
        </div>
        <div class="team-context__links">
          <a href="./#briefing">View latest briefing →</a>
          <a href="mailto:${CONTACT_EMAIL}">Contact the team</a>
        </div>
      </aside>
    </section>
  `;
}
