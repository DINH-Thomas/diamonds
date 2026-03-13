from __future__ import annotations

import os
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from availability_store import (
    DEFAULT_END_HOUR,
    DEFAULT_PARTICIPANTS,
    DEFAULT_START_HOUR,
    DEFAULT_TIMEZONE,
    DEFAULT_TITLE,
    SLOT_DURATION_HOURS,
    generate_schedule_dates,
    generate_slot_starts,
    STATUS_AVAILABLE,
    STATUS_MAYBE,
    STATUS_OPTIONS,
    STATUS_UNAVAILABLE,
    STATUS_UNKNOWN,
    Schedule,
    create_schedule,
    ensure_database,
    get_availability_entries,
    get_schedule,
    save_participant_entries,
)


DAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
WEEKDAY_COLUMNS_PER_TAB = 5


def format_day_label(current_date: date) -> str:
    return f"{DAY_LABELS[current_date.weekday()]} {current_date.strftime('%d/%m')}"


def format_hour_label(hour: int) -> str:
    return f"{hour:02d}:00"


def format_slot_label(hour: int) -> str:
    end_hour = hour + SLOT_DURATION_HOURS
    return f"{format_hour_label(hour)}-{end_hour:02d}:00"


def get_default_start_date() -> date:
    today = date.today()
    days_until_next_monday = (7 - today.weekday()) % 7
    if days_until_next_monday == 0:
        return today
    return today + timedelta(days=days_until_next_monday)


def infer_base_url() -> str:
    configured = os.environ.get("AVAILABILITY_BASE_URL")
    if configured:
        return configured.rstrip("/")

    port = st.get_option("server.port") or 8501
    return f"http://localhost:{port}"


def build_share_url(schedule_id: str) -> str:
    return f"{infer_base_url()}?schedule_id={schedule_id}"


def load_entries_frame(schedule_id: str) -> pd.DataFrame:
    entries = get_availability_entries(schedule_id)
    return pd.DataFrame(
        {
            "participant_name": entry.participant_name,
            "slot_start": entry.slot_start,
            "status": entry.status,
            "updated_at": entry.updated_at,
        }
        for entry in entries
    )


def get_schedule_dates(schedule: Schedule) -> list[date]:
    return generate_schedule_dates(schedule.start_date, schedule.days)


def chunk_schedule_dates(schedule_dates: list[date]) -> list[list[date]]:
    return [
        schedule_dates[index:index + WEEKDAY_COLUMNS_PER_TAB]
        for index in range(0, len(schedule_dates), WEEKDAY_COLUMNS_PER_TAB)
    ]


def filter_entries_to_visible_slots(schedule: Schedule, entries_frame: pd.DataFrame) -> pd.DataFrame:
    allowed_slots = set(generate_slot_starts(schedule.start_date, schedule.days, schedule.start_hour, schedule.end_hour))
    return entries_frame.loc[entries_frame["slot_start"].isin(allowed_slots)].copy()


def build_participant_grid(
    schedule: Schedule,
    participant_name: str,
    entries_frame: pd.DataFrame,
    dates: list[date],
) -> tuple[pd.DataFrame, list[date]]:
    participant_frame = entries_frame.loc[entries_frame["participant_name"] == participant_name]
    status_map = {
        slot_start: status
        for slot_start, status in zip(participant_frame["slot_start"], participant_frame["status"], strict=True)
    }
    rows: dict[str, list[str]] = {}

    for hour in range(schedule.start_hour, schedule.end_hour + 1, SLOT_DURATION_HOURS):
        hour_label = format_slot_label(hour)
        rows[hour_label] = []
        for current_date in dates:
            slot_start = datetime.combine(current_date, datetime.min.time()).replace(hour=hour)
            rows[hour_label].append(status_map.get(slot_start, STATUS_UNKNOWN))

    grid = pd.DataFrame(rows, index=[format_day_label(current_date) for current_date in dates]).transpose()
    grid.index.name = "Heure"
    return grid, dates


def flatten_grid(schedule: Schedule, edited_grid: pd.DataFrame, dates: list[date]) -> dict[datetime, str]:
    slot_statuses: dict[datetime, str] = {}
    hours = list(range(schedule.start_hour, schedule.end_hour + 1, SLOT_DURATION_HOURS))

    for row_index, hour in enumerate(hours):
        row_label = edited_grid.index[row_index]
        for column_index, current_date in enumerate(dates):
            column_label = edited_grid.columns[column_index]
            raw_status = edited_grid.loc[row_label, column_label]
            status = raw_status if raw_status in STATUS_OPTIONS else STATUS_UNKNOWN
            slot_start = datetime.combine(current_date, datetime.min.time()).replace(hour=hour)
            slot_statuses[slot_start] = status

    return slot_statuses


def build_summary_frame(entries_frame: pd.DataFrame) -> pd.DataFrame:
    summary_rows: list[dict[str, object]] = []

    for slot_start, slot_frame in entries_frame.groupby("slot_start", sort=True):
        available_names = sorted(
            slot_frame.loc[slot_frame["status"] == STATUS_AVAILABLE, "participant_name"].tolist()
        )
        maybe_names = sorted(
            slot_frame.loc[slot_frame["status"] == STATUS_MAYBE, "participant_name"].tolist()
        )
        unavailable_names = sorted(
            slot_frame.loc[slot_frame["status"] == STATUS_UNAVAILABLE, "participant_name"].tolist()
        )
        summary_rows.append(
            {
                "slot_start": slot_start,
                "date": slot_start.date(),
                "hour": slot_start.hour,
                "available_count": len(available_names),
                "maybe_count": len(maybe_names),
                "unavailable_count": len(unavailable_names),
                "score": len(available_names) + (0.5 * len(maybe_names)),
                "available_names": ", ".join(available_names) or "-",
                "maybe_names": ", ".join(maybe_names) or "-",
                "unavailable_names": ", ".join(unavailable_names) or "-",
            }
        )

    return pd.DataFrame(summary_rows).sort_values("slot_start").reset_index(drop=True)


def build_heatmap(schedule: Schedule, summary_frame: pd.DataFrame, dates: list[date]) -> go.Figure:
    hour_labels = [
        format_slot_label(hour)
        for hour in range(schedule.start_hour, schedule.end_hour + 1, SLOT_DURATION_HOURS)
    ]
    score_map = {
        row.slot_start: row.score
        for row in summary_frame.itertuples(index=False)
    }
    hover_map = {
        row.slot_start: (
            f"{row.available_count} dispo: {row.available_names}<br>"
            f"{row.maybe_count} peut-etre: {row.maybe_names}<br>"
            f"{row.unavailable_count} indispo: {row.unavailable_names}"
        )
        for row in summary_frame.itertuples(index=False)
    }

    z_values: list[list[float]] = []
    hover_values: list[list[str]] = []
    for hour in range(schedule.start_hour, schedule.end_hour + 1, SLOT_DURATION_HOURS):
        z_row: list[float] = []
        hover_row: list[str] = []
        for current_date in dates:
            slot_start = datetime.combine(current_date, datetime.min.time()).replace(hour=hour)
            z_row.append(float(score_map.get(slot_start, 0.0)))
            hover_row.append(hover_map.get(slot_start, "Aucune disponibilite renseignee."))
        z_values.append(z_row)
        hover_values.append(hover_row)

    figure = go.Figure(
        data=
        [
            go.Heatmap(
                z=z_values,
                x=[format_day_label(current_date) for current_date in dates],
                y=hour_labels,
                text=hover_values,
                hovertemplate="%{x}<br>%{y}<br>%{text}<extra></extra>",
                zmin=0,
                zmax=len(schedule.participants),
                colorscale=[
                    [0.0, "#f1f5f9"],
                    [0.01, "#dbe4ea"],
                    [0.35, "#f4c95d"],
                    [0.7, "#70a37f"],
                    [1.0, "#2f6b3b"],
                ],
                colorbar={"title": "Score"},
            )
        ]
    )
    figure.update_layout(
        margin={"l": 0, "r": 0, "t": 20, "b": 0},
        height=420,
        xaxis_title="Jour",
        yaxis_title="Heure",
    )
    return figure


def render_create_schedule_screen() -> None:
    st.title("Agenda de disponibilites")
    st.caption("Creez un planning partage sur 14 jours et diffusez le lien a votre equipe.")
    st.info(
        "Le lien partage depend de l'URL de l'app. En local, le lien pointe vers localhost. "
        "En production, definissez la variable AVAILABILITY_BASE_URL."
    )
    st.caption("Par defaut, l'agenda demarre le lundi suivant pour couvrir deux semaines ouvrees completes.")

    with st.form("create_schedule_form"):
        title = st.text_input("Nom de l'agenda", value=DEFAULT_TITLE)
        start_date = st.date_input("Date de debut", value=get_default_start_date())
        timezone = st.text_input("Fuseau horaire", value=DEFAULT_TIMEZONE)
        start_col, end_col = st.columns(2)
        with start_col:
            start_hour = st.number_input(
                "Premier debut de creneau",
                min_value=0,
                max_value=22,
                value=DEFAULT_START_HOUR,
                step=SLOT_DURATION_HOURS,
            )
        with end_col:
            end_hour = st.number_input(
                "Dernier debut de creneau",
                min_value=0,
                max_value=22,
                value=DEFAULT_END_HOUR,
                step=SLOT_DURATION_HOURS,
            )

        st.write("Participants")
        participant_columns = st.columns(2)
        participant_inputs: list[str] = []
        for index, default_name in enumerate(DEFAULT_PARTICIPANTS):
            with participant_columns[index % 2]:
                participant_inputs.append(
                    st.text_input(f"Participant {index + 1}", value=default_name)
                )

        submitted = st.form_submit_button("Creer l'agenda", use_container_width=True)

    if not submitted:
        return

    if end_hour < start_hour:
        st.error("Le dernier debut de creneau doit etre superieur ou egal au premier.")
        return

    if (int(end_hour) - int(start_hour)) % SLOT_DURATION_HOURS != 0:
        st.error("Les debuts de creneaux doivent respecter un pas de 2 heures.")
        return

    try:
        schedule_id = create_schedule(
            title=title,
            participants=participant_inputs,
            timezone=timezone,
            start_date=start_date,
            start_hour=int(start_hour),
            end_hour=int(end_hour),
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    st.query_params["schedule_id"] = schedule_id
    st.rerun()


def render_schedule(schedule: Schedule) -> None:
    schedule_dates = get_schedule_dates(schedule)
    if not schedule_dates:
        st.error("Aucun jour ouvrable n'est disponible sur la periode selectionnee.")
        return

    entries_frame = filter_entries_to_visible_slots(schedule, load_entries_frame(schedule.schedule_id))
    summary_frame = build_summary_frame(entries_frame)
    share_url = build_share_url(schedule.schedule_id)
    slots_per_day = len(range(schedule.start_hour, schedule.end_hour + 1, SLOT_DURATION_HOURS))
    total_slots = len(schedule_dates) * slots_per_day
    date_chunks = chunk_schedule_dates(schedule_dates)

    st.title(schedule.title)
    st.caption(
        f"Agenda partage sur {schedule.days} jours, fuseau {schedule.timezone}, tranches de {SLOT_DURATION_HOURS}h "
        f"de {format_slot_label(schedule.start_hour)} a {format_slot_label(schedule.end_hour)}, week-ends exclus."
    )

    with st.sidebar:
        st.subheader("Lien partage")
        st.code(share_url, language=None)
        st.link_button("Ouvrir le lien", share_url)
        st.caption("Partagez ce lien dans Slack pour que chacun modifie le meme agenda.")

        st.divider()
        st.subheader("Participants")
        for participant in schedule.participants:
            completed_slots = int(
                entries_frame.loc[
                    (entries_frame["participant_name"] == participant)
                    & (entries_frame["status"] != STATUS_UNKNOWN)
                ].shape[0]
            )
            st.write(f"{participant}: {completed_slots}/{total_slots} creneaux renseignes")

        if st.button("Creer un nouvel agenda", use_container_width=True):
            st.query_params.clear()
            st.rerun()

    overview_col, summary_col = st.columns([1.1, 1])
    with overview_col:
        st.markdown(
            f"""
            **Periode**: {format_day_label(schedule_dates[0])} au
            {format_day_label(schedule_dates[-1])}
            """
        )
        st.write("Participants: " + ", ".join(schedule.participants))
    with summary_col:
        best_score = float(summary_frame["score"].max()) if not summary_frame.empty else 0.0
        best_slots = int(summary_frame.loc[summary_frame["score"] == best_score].shape[0]) if best_score else 0
        st.metric("Meilleur score de groupe", f"{best_score:.1f}/{len(schedule.participants)}")
        st.metric("Creneaux au meilleur score", best_slots)

    st.divider()
    participant_name = st.segmented_control(
        "Je modifie les disponibilites de",
        options=schedule.participants,
        default=schedule.participants[0],
        selection_mode="single",
    )
    st.caption(
        f"Chaque case represente une tranche de {SLOT_DURATION_HOURS}h. Le score de synthese compte 1 pour Disponible, "
        "0.5 pour Peut-etre et 0 pour Indisponible ou Non renseigne."
    )

    week_tabs = st.tabs([f"Semaine {index + 1}" for index in range(len(date_chunks))])
    edited_weeks: list[tuple[pd.DataFrame, list[date]]] = []
    for tab, week_dates in zip(week_tabs, date_chunks, strict=True):
        with tab:
            week_grid, week_dates = build_participant_grid(schedule, participant_name, entries_frame, week_dates)
            edited_grid = st.data_editor(
                week_grid,
                use_container_width=True,
                hide_index=False,
                key=f"editor_{schedule.schedule_id}_{participant_name}_{week_dates[0].isoformat()}",
                column_config={
                    column_name: st.column_config.SelectboxColumn(
                        column_name,
                        options=STATUS_OPTIONS,
                        required=True,
                        width="medium",
                    )
                    for column_name in week_grid.columns
                },
            )
            edited_weeks.append((edited_grid, week_dates))

    save_clicked = st.button("Enregistrer les disponibilites", type="primary", use_container_width=True)
    if save_clicked:
        slot_statuses: dict[datetime, str] = {}
        for edited_grid, week_dates in edited_weeks:
            slot_statuses.update(flatten_grid(schedule, edited_grid, week_dates))
        try:
            save_participant_entries(schedule, participant_name, slot_statuses)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.success(f"Disponibilites de {participant_name} enregistrees.")
        st.rerun()

    st.divider()
    st.subheader("Vue de synthese")
    heatmap_labels = [f"Heatmap semaine {index + 1}" for index in range(len(date_chunks))] + ["Meilleurs creneaux"]
    heatmap_tabs = st.tabs(heatmap_labels)
    for tab, week_dates in zip(heatmap_tabs[:-1], date_chunks, strict=True):
        with tab:
            st.plotly_chart(build_heatmap(schedule, summary_frame, week_dates), use_container_width=True)
    with heatmap_tabs[-1]:
        top_slots = (
            summary_frame.sort_values(["score", "available_count", "maybe_count", "slot_start"], ascending=[False, False, False, True])
            .head(12)
            .assign(
                creneau=lambda frame: frame["slot_start"].dt.strftime("%a %d/%m %H:%M")
                + "-"
                + (frame["slot_start"] + pd.Timedelta(hours=SLOT_DURATION_HOURS)).dt.strftime("%H:%M"),
                disponibles=lambda frame: frame["available_names"],
                peut_etre=lambda frame: frame["maybe_names"],
            )[["creneau", "score", "disponibles", "peut_etre"]]
        )
        st.dataframe(top_slots, use_container_width=True, hide_index=True)

    export_frame = entries_frame.assign(
        slot_start=entries_frame["slot_start"].dt.strftime("%Y-%m-%d %H:%M"),
        slot_end=(entries_frame["slot_start"] + pd.Timedelta(hours=SLOT_DURATION_HOURS)).dt.strftime("%Y-%m-%d %H:%M"),
        updated_at=entries_frame["updated_at"].dt.strftime("%Y-%m-%d %H:%M:%S"),
    )
    st.download_button(
        "Exporter le CSV",
        data=export_frame.to_csv(index=False).encode("utf-8"),
        file_name=f"agenda_{schedule.schedule_id}.csv",
        mime="text/csv",
        use_container_width=True,
    )


st.set_page_config(page_title="Agenda partage", layout="wide")
ensure_database()

schedule_id = st.query_params.get("schedule_id")
if isinstance(schedule_id, list):
    schedule_id = schedule_id[0] if schedule_id else None

if not schedule_id:
    render_create_schedule_screen()
else:
    loaded_schedule = get_schedule(str(schedule_id))
    if loaded_schedule is None:
        st.error("Cet agenda est introuvable. Creez-en un nouveau ou verifiez le lien partage.")
        if st.button("Creer un nouvel agenda", use_container_width=True):
            st.query_params.clear()
            st.rerun()
    else:
        render_schedule(loaded_schedule)
