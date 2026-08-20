const CONTACT_EMAIL = "raj.ayush@students.iiserpune.ac.in";

interface TeamMember {
  name: string;
  role: string;
  affiliation: string;
  scdldsRole?: string;
  expertise: string;
  image: string;
  imagePosition?: string;
  profile: string;
  email: string;
}

const SCIENTIFIC_TEAM: TeamMember[] = [
  {
    name: "Sandeep Juneja",
    role: "Professor of Computer Science · Centre Director",
    affiliation: "Ashoka University",
    scdldsRole: "Centre Director",
    expertise: "Applied probability, machine learning, and monsoon weather modelling.",
    image: "./team/sandeep-juneja.jpg",
    profile: "https://www.ashoka.edu.in/profile/sandeep-juneja/",
    email: "sandeep.juneja@ashoka.edu.in",
  },
  {
    name: "Parthasarathi Mukhopadhyay",
    role: "Visiting Faculty · Earth & Environmental Sciences",
    affiliation: "IISER Berhampur · FASc",
    scdldsRole: "Collaborator",
    expertise: "Numerical weather prediction, monsoon modelling, clouds, and convection.",
    image: "./team/parthasarathi-mukhopadhyay.jpg",
    imagePosition: "center 18%",
    profile: "https://www.iiserbpr.ac.in/people/profile/parthasarathym",
    email: "parthasarathym@iiserbpr.ac.in",
  },
  {
    name: "Dr. Manmeet Singh",
    role: "Project Lead · Assistant Professor",
    affiliation: "Western Kentucky University",
    scdldsRole: "Project Lead",
    expertise: "AI for climate and disaster science, weather prediction, and Earth system modelling.",
    image: "./team/manmeet-singh.jpg",
    imagePosition: "center 18%",
    profile: "https://www.wku.edu/eeas/staff/manmeet_singh",
    email: "manmeet.singh@wku.edu",
  },
  {
    name: "Ayush Raj",
    role: "MS Thesis Researcher · AI Weather Research",
    affiliation: "IISER Pune",
    scdldsRole: "Researcher",
    expertise: "AI subseasonal-to-seasonal weather prediction and forecast website development.",
    image: "./team/ayush-raj.webp",
    profile: "https://in.linkedin.com/in/ayush-raj-7608a424a",
    email: CONTACT_EMAIL,
  },
  {
    name: "Saptarishi Dhanuka",
    role: "Pre-doctoral Fellow",
    affiliation: "Ashoka University",
    scdldsRole: "Pre-doctoral Fellow",
    expertise: "Artificial intelligence for weather, climate, and data-driven forecasting.",
    image: "./team/saptarishi-dhanuka.jpg",
    imagePosition: "center 20%",
    profile: "https://www.ashoka.edu.in/profile/saptarishi-dhanuka/",
    email: "saptarishi.dhanuka@ashoka.edu.in",
  },
];

function renderMember(member: TeamMember): string {
  const imageStyle = member.imagePosition
    ? ` style="object-position: ${member.imagePosition}"`
    : "";

  return `
    <article class="team-person-card">
      <a
        class="team-person-card__portrait"
        href="${member.profile}"
        target="_blank"
        rel="noreferrer"
        aria-label="View ${member.name}'s official profile"
      >
        <img src="${member.image}" alt="${member.name}" loading="eager" decoding="async"${imageStyle} />
        <span class="team-person-card__view" aria-hidden="true">Profile ↗</span>
      </a>
      <div class="team-person-card__body">
        <h3>${member.name}</h3>
        <p class="team-person-card__role">${member.role}</p>
        <div class="team-person-card__affiliations">
          <span class="team-card-label">${member.affiliation}</span>
          ${
            member.scdldsRole
              ? `<a
                  class="team-centre-affiliation"
                  href="https://scdlds.ashoka.edu.in/"
                  target="_blank"
                  rel="noreferrer"
                  aria-label="${member.scdldsRole}, Safexpress Centre for Data, Learning and Decision Sciences"
                ><span aria-hidden="true"></span>SCDLDS · ${member.scdldsRole}</a>`
              : ""
          }
        </div>
        <p>${member.expertise}</p>
        <div class="team-person-card__links">
          <a href="${member.profile}" target="_blank" rel="noreferrer">Official profile <span aria-hidden="true">↗</span></a>
          <a href="mailto:${member.email}">Email</a>
        </div>
      </div>
    </article>
  `;
}

export function renderTeamPage(container: HTMLElement): void {
  container.innerHTML = `
    <section class="team-page" aria-labelledby="team-title">
      <header class="team-hero">
        <span class="team-eyebrow">S2S Research</span>
        <h1 id="team-title">People behind the forecast.</h1>
        <p class="team-hero__intro">
          Atmospheric science, machine learning, and forecast verification for
          experimental subseasonal guidance.
        </p>
      </header>

      <section class="team-roster" aria-labelledby="team-roster-title">
        <header class="team-section-heading">
          <span class="team-eyebrow">People behind the forecast</span>
          <h2 id="team-roster-title">Scientific team and collaborators</h2>
          <p>Official profiles and direct contact details are available below.</p>
        </header>
        <div class="team-grid">
          ${SCIENTIFIC_TEAM.map(renderMember).join("")}
        </div>
      </section>

      <footer class="team-page-footer" aria-label="Institutional collaboration and contact">
        <div class="team-page-footer__logos">
          <img
            src="./brand/scdlds-centre.png"
            alt="Safexpress Centre for Data, Learning and Decision Sciences"
          />
          <span aria-hidden="true"></span>
          <img src="./brand/ashoka-university.png" alt="Ashoka University" />
        </div>
        <p>
          Developed in association with the Safexpress Centre for Data, Learning
          and Decision Sciences at Ashoka University.
        </p>
        <div class="team-page-footer__links">
          <a href="https://scdlds.ashoka.edu.in/" target="_blank" rel="noreferrer">
            Centre website <span aria-hidden="true">↗</span>
          </a>
          <a href="mailto:${CONTACT_EMAIL}">Contact the team</a>
        </div>
      </footer>
    </section>
  `;
}
