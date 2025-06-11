# import requests
# from django.conf import settings
# from django.db import IntegrityError
#
# from characters.models import Character
#
#
# def scrape_characters() -> list[Character]:
#     next_url_to_scrape = settings.RICK_AND_MORTY_API_CHARACTERS_URL
#
#     characters = []
#     while next_url_to_scrape is not None:
#         characters_response = requests.get(next_url_to_scrape).json()
#         for character_dict in characters_response["results"]:
#             characters.append(
#                 Character(
#                     api_id=character_dict["id"],
#                     name=character_dict["name"],
#                     status=character_dict["status"],
#                     species=character_dict["species"],
#                     gender=character_dict["gender"],
#                     image=character_dict["image"],
#                 )
#             )
#         next_url_to_scrape = characters_response["info"]["next"]
#
#     return characters
#
#
# def save_characters(characters: list[Character]) -> None:
#     for character in characters:
#         try:
#             character.save()
#         except IntegrityError:
#             print(f"Character with api_id: {character.api_id} already exists in DB!")
#
#
# def sync_characters_with_api() -> None:
#     characters = scrape_characters()
#     save_characters(characters)

# Щоб пришвидшити процес скрапингу ми можемо використати модуль httpx:
import asyncio
import time

import httpx
from django.conf import settings
from httpx import AsyncClient

from characters.models import Character


GRAPHQL_QUERY = """
query {
  characters(page: %s) {
    info{
      pages
    }
    results{
      api_id: id
      name
      status
      gender
      image
    }
  }
}
"""


def parse_characters_response(characters_response: dict) -> list[Character]:
    return [
        Character(**character_dict)
        for character_dict in characters_response["data"]["characters"]["results"]
    ]


async def scrape_single_page(
    client: AsyncClient, url_to_scrape: str, page: int
) -> list[Character]:
    characters_response = (
        await client.post(url_to_scrape, data={"query": GRAPHQL_QUERY % str(page)})
    ).json()
    return parse_characters_response(characters_response)


async def scrape_characters() -> list[Character]:
    start = time.perf_counter()

    url_to_scrape = settings.RICK_AND_MORTY_API_CHARACTERS_URL

    characters_response = httpx.post(
        url_to_scrape, data={"query": GRAPHQL_QUERY % "1"}
    ).json()
    num_pages = characters_response["data"]["characters"]["info"]["pages"]
    characters = parse_characters_response(characters_response)

    async with httpx.AsyncClient() as client:
        characters.extend(
            sum(
                await asyncio.gather(
                    *[
                        scrape_single_page(client, url_to_scrape, page)
                        for page in range(2, num_pages + 1)
                    ]
                ),
                [],
            )
        )

        end = time.perf_counter()
        print("Elapsed for scraping:", end - start)

        return characters


async def save_characters(characters: list[Character]) -> None:
    start = time.perf_counter()

    await Character.objects.abulk_create(characters, ignore_conflicts=True)

    end = time.perf_counter()
    print("Elapsed for saving:", end - start)


async def sync_characters_with_api() -> None:
    characters = await scrape_characters()
    await save_characters(characters)
