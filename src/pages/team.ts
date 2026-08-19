const CONTACT_EMAIL = "raj.ayush@students.iiserpune.ac.in";

interface TeamMember {
  name: string;
  role: string;
  affiliation: string;
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
    affiliation: "Ashoka University · SCDLDS",
    expertise: "Applied probability, machine learning, and monsoon weather modelling.",
    image: "./team/sandeep-juneja.jpg",
    profile: "https://www.ashoka.edu.in/profile/sandeep-juneja/",
    email: "sandeep.juneja@ashoka.edu.in",
  },
  {
    name: "Bedartha Goswami",
    role: "Assistant Professor · Data Science",
    affiliation: "IISER Pune",
    expertise: "Machine learning for weather and climate, with a focus on complex systems.",
    image: "./team/bedartha-goswami.jpg",
    imagePosition: "center 34%",
    profile:
      "https://www.iiserpune.ac.in/research/department/data-science/people/faculty/regular-faculty/bedartha-goswami/542",
    email: "bedartha.goswami@iiserpune.ac.in",
  },
  {
    name: "Parthasarathi Mukhopadhyay",
    role: "Visiting Faculty · Earth & Environmental Sciences",
    affiliation: "IISER Berhampur · FASc",
    expertise: "Numerical weather prediction, monsoon modelling, clouds, and convection.",
    image: "./team/parthasarathi-mukhopadhyay.jpg",
    imagePosition: "center 18%",
    profile: "https://www.iiserbpr.ac.in/people/profile/parthasarathym",
    email: "parthasarathym@iiserbpr.ac.in",
  },
  {
    name: "Saptarishi Dhanuka",
    role: "Pre-doctoral Fellow",
    affiliation: "SCDLDS · Ashoka University",
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
        <img src="${member.image}" alt="${member.name}" loading="lazy"${imageStyle} />
        <span aria-hidden="true">View profile ↗</span>
      </a>
      <div class="team-person-card__body">
        <span class="team-card-label">${member.affiliation}</span>
        <h3>${member.name}</h3>
        <p class="team-person-card__role">${member.role}</p>
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
        <div>
          <span class="team-eyebrow">People behind the forecast</span>
          <h1 id="team-title">The team behind the forecast.</h1>
        </div>
        <p>
          S2S Research brings atmospheric science, machine learning, forecast
          verification, and careful public communication together in one
          experimental service.
        </p>
      </header>

      <article class="team-lead" aria-labelledby="team-lead-name">
        <div class="team-lead__portrait" aria-hidden="true">
          <span>AR</span>
          <small>Project lead</small>
        </div>
        <div class="team-lead__content">
          <span class="team-card-label">Lead researcher &amp; developer</span>
          <h2 id="team-lead-name">Ayush Raj</h2>
          <p class="team-lead__affiliation">
            IISER Pune · Safexpress Centre for Data, Learning and Decision Sciences
          </p>
          <p>
            Ayush leads the research engineering behind S2S Research—from forecast
            pipelines and scientific validation to operational automation and the
            public-facing products that make subseasonal guidance easier to use.
          </p>
          <div class="team-lead__links">
            <a href="mailto:${CONTACT_EMAIL}">Email Ayush</a>
            <a href="https://in.linkedin.com/in/ayush-raj-7608a424a" target="_blank" rel="noreferrer">
              LinkedIn <span aria-hidden="true">↗</span>
            </a>
          </div>
        </div>
        <div class="team-lead__mark" aria-hidden="true">01</div>
      </article>

      <section class="team-roster" aria-labelledby="team-roster-title">
        <header class="team-section-heading">
          <div>
            <span class="team-eyebrow">Scientific leadership &amp; collaborators</span>
            <h2 id="team-roster-title">Expertise across weather, climate, data, and decisions.</h2>
          </div>
          <p>Official institutional profiles and direct contact details are provided for every collaborator.</p>
        </header>
        <div class="team-grid">
          ${SCIENTIFIC_TEAM.map(renderMember).join("")}
        </div>
      </section>

      <aside class="team-institution-band" aria-label="Institutional collaboration">
        <div class="team-institution-band__logos">
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
        <a href="https://scdlds.ashoka.edu.in/" target="_blank" rel="noreferrer">
          Visit the Centre <span aria-hidden="true">↗</span>
        </a>
      </aside>

      <section class="team-principles" aria-labelledby="team-principles-title">
        <header>
          <span class="team-eyebrow">How we work</span>
          <h2 id="team-principles-title">From research run to public guidance</h2>
        </header>
        <div class="team-principles__grid">
          <article>
            <span>01</span>
            <h3>Scientific provenance</h3>
            <p>Every issue records its initialization source, ensemble size, and valid forecast periods.</p>
          </article>
          <article>
            <span>02</span>
            <h3>Validation before release</h3>
            <p>Forecast packages pass data, checksum, and presentation checks before they can be published.</p>
          </article>
          <article>
            <span>03</span>
            <h3>Transparent limitations</h3>
            <p>Research status, calibration gaps, and source delays stay visible alongside the guidance.</p>
          </article>
        </div>
      </section>

      <section class="team-contact" aria-labelledby="team-contact-title">
        <div>
          <span class="team-card-label">Research enquiries</span>
          <h2 id="team-contact-title">Questions, collaboration, or feedback?</h2>
        </div>
        <a href="mailto:${CONTACT_EMAIL}">Contact the team <span aria-hidden="true">→</span></a>
      </section>
    </section>
  `;
}
