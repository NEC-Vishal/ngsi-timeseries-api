from exceptions.exceptions import NGSIUsageError, InvalidParameterValue
from flask import request
from reporter.reporter import _validate_query_params
from translators.factory import translator_for
import logging
from .geo_query_handler import handle_geo_query
from utils.jsondict import lookup_string_match
import dateutil.parser
from datetime import datetime, timezone


def query_1TNENA(entity_type=None,  # In Path
                 id_=None,  # In Query
                 attrs=None,
                 aggr_method=None,
                 aggr_period=None,
                 aggr_scope=None,
                 options=None,
                 from_date=None,
                 to_date=None,
                 last_n=None,
                 limit=10000,
                 offset=0,
                 georel=None,
                 geometry=None,
                 coords=None):
    """
    See /types/{entityType} in API Specification
    quantumleap.yml
    """
    r, c = _validate_query_params(attrs,
                                  aggr_period,
                                  aggr_method,
                                  aggr_scope,
                                  options)
    if c != 200:
        return r, c

    r, c, geo_query = handle_geo_query(georel, geometry, coords)
    if r:
        return r, c

    if attrs is not None:
        attrs = attrs.split(',')

    fiware_s = request.headers.get('fiware-service', None)
    fiware_sp = request.headers.get('fiware-servicepath', None)

    entities = None
    entity_ids = None
    if id_:
        entity_ids = [s.strip() for s in id_.split(',') if s]
    try:
        with translator_for(fiware_s) as trans:
            entities = trans.query(attr_names=attrs,
                                   entity_type=entity_type,
                                   entity_ids=entity_ids,
                                   aggr_method=aggr_method,
                                   aggr_period=aggr_period,
                                   aggr_scope=aggr_scope,
                                   from_date=from_date,
                                   to_date=to_date,
                                   last_n=last_n,
                                   limit=limit,
                                   offset=offset,
                                   fiware_service=fiware_s,
                                   fiware_servicepath=fiware_sp,
                                   geo_query=geo_query)
    except NGSIUsageError as e:
        return {
            "error": "{}".format(type(e)),
            "description": str(e)
        }, 400

    except InvalidParameterValue as e:
        return {
            "error": "{}".format(type(e)),
            "description": str(e)
        }, 422

    except Exception as e:
        msg = "Something went wrong with QL. Error: {}".format(e)
        logging.getLogger().error(msg, exc_info=True)
        return msg, 500

    if entities:
        res = _prepare_response(entities,
                                attrs,
                                entity_type,
                                entity_ids,
                                aggr_method,
                                aggr_period,
                                from_date,
                                to_date,)
        return res

    r = {
        "error": "Not Found",
        "description": "No records were found for such query."
    }
    return r, 404


def _prepare_response(entities, attrs, entity_type, entity_ids,
                      aggr_method, aggr_period, from_date, to_date):
    entries = []
    ignore = ('type', 'id', 'index')
    for e in entities:
        attributes = []
        attrs = [at for at in sorted(e.keys()) if at not in ignore]
        for at in attrs:
            attributes.append({
                'attrName': at,
                'values': e[at]['values']
            })
        try:
            f_date = dateutil.parser.isoparse(from_date).replace(tzinfo=timezone.utc).isoformat()
        except Exception as ex:
            f_date = ''
        try:
            t_date = dateutil.parser.isoparse(to_date).replace(tzinfo=timezone.utc).isoformat()
        except Exception as ex:
            t_date = ''
        index = [f_date, t_date] if aggr_method and not aggr_period else e['index']
        entity = {
                 'entityId': e['id'],
                 'index': index,
                 'attributes': attributes
        }
        entries.append(entity)
    res = {
        'entityType': entity_type,
        'entities': entries
    }
    return res

def query_1TNENA_value(*args, **kwargs):
    res = query_1TNENA(*args, **kwargs)
    if isinstance(res, dict):
        res.pop('entityType', None)
        res['values'] = res['entities']
        res.pop('entities', None)
    return res
