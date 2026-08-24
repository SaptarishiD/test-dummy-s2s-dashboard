const CONTACT_EMAIL = "raj.ayush@students.iiserpune.ac.in";

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
    name: "Ayush Raj",
    projectRole: "Main Researcher",
    professionalTitle: "MS Thesis Researcher · AI weather research",
    affiliation: "IISER Pune · SCDLDS",
    expertise: "AI subseasonal-to-seasonal prediction, forecast verification, and dashboard development.",
    image: "./team/ayush-raj.webp",
    profile: "https://in.linkedin.com/in/ayush-raj-7608a424a",
  },
  {
    name: "Sandeep Juneja",
    projectRole: "Senior Scientist",
    professionalTitle: "Professor of Computer Science · Centre Director",
    affiliation: "Ashoka University · SCDLDS",
    expertise: "Applied probability, machine learning, and monsoon weather modelling.",
    image: "./team/sandeep-juneja.jpg",
    profile: "https://www.ashoka.edu.in/profile/sandeep-juneja/",
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
    name: "Saptarishi Dhanuka",
    projectRole: "Research Contributor",
    professionalTitle: "Pre-doctoral Fellow · AI weather research",
    affiliation: "Ashoka University · SCDLDS",
    expertise: "Artificial intelligence for weather, climate, and data-driven forecasting.",
    image: "./team/saptarishi-dhanuka.jpg",
    imagePosition: "center 20%",
    profile: "https://www.ashoka.edu.in/profile/saptarishi-dhanuka/",
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
        <span class="team-person-card__project-role">${member.projectRole}</span>
        <h3>${member.name}</h3>
        <p class="team-person-card__role">${member.professionalTitle}</p>
        <p class="team-person-card__affiliation">${member.affiliation}</p>
        <p class="team-person-card__expertise">${member.expertise}</p>
        <a
          class="team-person-card__profile"
          href="${member.profile}"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Open ${member.name}'s public profile in a new tab"
        >Public profile <span aria-hidden="true">↗</span></a>
      </div>
    </article>
  `;
}

export function renderTeamPage(container: HTMLElement): void {
  container.innerHTML = `
    <section class="team-page" aria-labelledby="team-title">
      <header class="team-hero">
        <span class="team-eyebrow">Scientific team</span>
        <h1 id="team-title">Scientific contributors</h1>
        <p class="team-hero__intro">
          Contributors to experimental subseasonal forecasting research.
        </p>
      </header>

      <section class="team-roster" aria-label="Contributors ordered by project responsibility">
        <div class="team-grid">
          ${SCIENTIFIC_TEAM.map(renderMember).join("")}
        </div>
      </section>

      <aside class="team-context" aria-label="Research context and team links">
        <div>
          <span>Scientific context</span>
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
